import customtkinter as ctk
import json
import uuid
import keyboard
import threading
import time
import os
import get_win_info
from PIL import Image, ImageTk
import pystray
import queue

SETTINGS_FILE = "settings.json"
STATE_FILE = "state.json"
stop_event = threading.Event()

# JSONファイルを読み込む関数
def load_settings(filename):
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(settings_path):
        return []
    with open(settings_path, 'r') as file:
        return json.load(file)

# JSONファイルに設定を保存する関数
def save_settings(filename, settings):
    with open(filename, 'w') as file:
        json.dump(settings, file, indent=4)

# 状態を保存する関数
def save_state(state):
    with open(STATE_FILE, 'w') as file:
        json.dump(state, file)

# 状態を読み込む関数
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as file:
            return json.load(file)
    return {}

# キー入力の検証関数
def is_valid_key(key):
    try:
        keyboard.key_to_scan_codes(key)
        return True
    except ValueError:
        return False

# hot_keyの検証関数
def is_valid_hotkey(key):
    try:
        keyboard.parse_hotkey(key)
        return True
    except ValueError:
        return False

def remap_key(src, dst, active_process, settings):
    def handler(event):
        if event.event_type == keyboard.KEY_DOWN:
            if get_win_info.get_active_process_name() == active_process:
                keyboard.press_and_release(dst)
                return False  # キーイベントをキャンセルしてホットキーを送信
        return True  # それ以外の場合はキーイベントをキャンセルしない
    return keyboard.hook_key(src, handler, suppress=True)

def key_transformer():
    settings = load_settings(SETTINGS_FILE)
    hooks = []
    for setting in settings:
        if setting['original_key'] and setting['hot_key']:
            hook = remap_key(setting['original_key'], setting['hot_key'], setting['app'], settings)
            hooks.append(hook)
    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for hook in hooks:
            keyboard.unhook(hook)
        print("Stopped key transformer.")

key_transformer_thread = None
is_transformer_running = load_state().get("is_running", False)

def start_key_transformer():
    global key_transformer_thread, is_transformer_running
    if key_transformer_thread is None or not key_transformer_thread.is_alive():
        stop_event.clear()
        key_transformer_thread = threading.Thread(target=key_transformer, name="KeyTransformerThread")
        key_transformer_thread.start()
        is_transformer_running = True
        save_state({"is_running": is_transformer_running})
        print("Key transformer started.")

def stop_key_transformer():
    global key_transformer_thread, is_transformer_running
    for thread in threading.enumerate():
        if thread.name == "KeyTransformerThread":
            stop_event.set()
            thread.join()
            key_transformer_thread = None
            is_transformer_running = False
            save_state({"is_running": is_transformer_running})
            print("Key transformer stopped.")
            return

class KeyTransformerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Key Transformer")
        self.geometry("500x600")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.dropdown_var = ctk.StringVar()
        self.dropdown = ctk.CTkComboBox(master=self, values=[], variable=self.dropdown_var, command=self.on_change)
        self.dropdown.pack(pady=10)

        visible_windows = get_win_info.get_open_windows()
        for process_name in visible_windows:
            current_values = list(self.dropdown.cget("values"))
            current_values.append(process_name)
            self.dropdown.configure(values=current_values)

        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.pack(expand=True, fill="both")

        self.add_button = ctk.CTkButton(self, text="Add Row", command=self.add_row)
        self.add_button.pack(pady=10)

        self.start_button = ctk.CTkButton(self, text="Start", command=start_key_transformer)
        self.start_button.pack(pady=10)

        self.stop_button = ctk.CTkButton(self, text="Stop", command=stop_key_transformer)
        self.stop_button.pack(pady=10)

        self.update_table()

        self.queue = queue.Queue()
        self.after(0, self.process_queue)

    def process_queue(self):
        try:
            while True:
                func, args = self.queue.get_nowait()
                func(*args)
        except queue.Empty:
            self.after(100, self.process_queue)

    def on_change(self, value):
        self.update_table()

    def add_row(self):
        selected_app = self.dropdown_var.get()
        if selected_app:
            new_uid = str(uuid.uuid4())
            new_row = {
                "uid": new_uid,
                "app": selected_app,
                "original_key": "",
                "hot_key": ""
            }
            settings = load_settings(SETTINGS_FILE)
            settings.append(new_row)
            save_settings(SETTINGS_FILE, settings)
            self.update_table()

    def delete_row(self, uid):
        settings = load_settings(SETTINGS_FILE)
        settings = [setting for setting in settings if setting['uid'] != uid]
        save_settings(SETTINGS_FILE, settings)
        self.update_table()

    def update_table(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        settings = load_settings(SETTINGS_FILE)
        selected_app = self.dropdown_var.get()
        for setting in settings:
            if setting['app'] == selected_app:
                row_frame = ctk.CTkFrame(self.table_frame)
                row_frame.pack(fill="x", pady=5)

                original_key_button = ctk.CTkButton(row_frame, text=setting['original_key'] or "set original key",
                                                    command=lambda s=setting: self.open_dialog(s['uid'], "original_key"))
                original_key_button.pack(side="left", expand=True, fill="x")

                hot_key_button = ctk.CTkButton(row_frame, text=setting['hot_key'] or "set hot key",
                                               command=lambda s=setting: self.open_dialog(s['uid'], "hot_key"))
                hot_key_button.pack(side="left", expand=True, fill="x")

                delete_button = ctk.CTkButton(row_frame, text="Delete", command=lambda uid=setting['uid']: self.delete_row(uid))
                delete_button.pack(side="left", padx=5)

    def open_dialog(self, uid, key):
        dialog = ctk.CTkToplevel(self)
        dialog.geometry("300x150")

        settings = load_settings(SETTINGS_FILE)
        selected_row = next(setting for setting in settings if setting['uid'] == uid)
        current_value = selected_row[key]

        key_input = ctk.CTkEntry(dialog, width=200)
        key_input.insert(0, current_value)
        key_input.pack(pady=10)

        hotkeys = []
        modifiers = {"shift", "ctrl", "alt", "windows"}

        def on_key(event):
            key_name = event.name
            if key == "original_key":
                self.queue.put((key_input.delete, (0, ctk.END)))
                self.queue.put((key_input.insert, (0, key_name)))
            else:
                if event.event_type == "down":
                    if key_name == ",":
                        key_name = "comma"
                    elif key_name == "+":
                        key_name = "plus"
                    if len(hotkeys) == 0:
                        hotkeys.append(key_name)
                    elif len(hotkeys) >= 1:
                        if hotkeys[-1] in modifiers:
                            hotkeys.append("+")
                            if key_name != hotkeys[-2]:
                                hotkeys.append(key_name)
                        elif hotkeys[-1] == "+":
                            if key_name != hotkeys[-2]:
                                hotkeys.append(key_name)
                        elif hotkeys[-1] != "+":
                            hotkeys.append(",")
                            hotkeys.append(key_name)
                    hotkey = "".join(hotkeys)
                    self.queue.put((key_input.delete, (0, ctk.END)))
                    self.queue.put((key_input.insert, (0, hotkey)))

        hook = keyboard.hook(on_key)

        def save_key():
            new_key = key_input.get()
            if (key == "original_key" and is_valid_key(new_key)) or (key == "hot_key" and is_valid_hotkey(new_key)):
                selected_row[key] = new_key
                save_settings(SETTINGS_FILE, settings)
                keyboard.unhook(hook)
                dialog.destroy()
                self.update_table()
            else:
                error_label.configure(text="Invalid key. Please enter a valid key.")

        def reset_dlg():
            key_input.delete(0, ctk.END)
            hotkeys.clear()

        def close_dlg():
            keyboard.unhook(hook)
            dialog.destroy()
        # バツボタンで閉じるときにフックを解除
        def on_closing():
            keyboard.unhook(hook)
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_closing)

        save_button = ctk.CTkButton(dialog, text="Save", command=save_key)
        save_button.pack(side="left", padx=10, pady=10)

        cancel_button = ctk.CTkButton(dialog, text="Cancel", command=close_dlg)
        cancel_button.pack(side="left", padx=10, pady=10)

        reset_button = ctk.CTkButton(dialog, text="Reset", command=reset_dlg)
        reset_button.pack(side="left", padx=10, pady=10)
        error_label = ctk.CTkLabel(dialog, text="", text_color="red")
        error_label.pack()

    def on_closing(self):
        self.withdraw()
        self.create_tray_icon()

    def create_tray_icon(self):
        image = Image.open("./assets/icon.png")
        icon = pystray.Icon("KeyTransformer", image, "Key Transformer", self.create_menu())
        icon.run()

    def create_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Open", self.show_window),
            pystray.MenuItem("Exit", self.exit_app)
        )

    def show_window(self, icon, item):
        self.deiconify()
        icon.stop()

    def exit_app(self, icon, item):
        stop_key_transformer()
        self.destroy()
        icon.stop()

if __name__ == "__main__":
    app = KeyTransformerApp()
    if is_transformer_running:
        start_key_transformer()
    app.mainloop()
