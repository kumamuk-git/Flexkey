import flet as ft
import get_win_info
import json
import uuid
import keyboard
import psutil
import os
import multiprocessing
import threading
import time

p: ft.Page

SETTINGS_FILE = "settings.json"
# 停止フラグを作成
stop_event = threading.Event()

#####################################################################################
#####################################################################################

# JSONファイルを読み込む関数
def load_settings(filename):
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILE)
    if not os.path.exists(settings_path):
        return []
    with open(filename, 'r') as file:
        return json.load(file)
    
# JSONファイルに設定を保存する関数
def save_settings(filename, settings):
    with open(filename, 'w') as file:
        json.dump(settings, file, indent=4)

#####################################################################################
#####################################################################################
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
    
#####################################################################################
#####################################################################################
def remap_key(src, dst, active_process, settings):
    def handler(event):
        if event.event_type == keyboard.KEY_DOWN:
            if get_win_info.get_active_process_name() == active_process:
                keyboard.press_and_release(dst)
                return False  # キーイベントをキャンセルしてホットキーを送信
        return True  # それ以外の場合はキーイベントをキャンセルしない
    return keyboard.hook_key(src, handler, suppress=True)

# メインロジック
def key_transformer():
    settings = load_settings('settings.json')
    # 各キーを設定
    hooks = []
    for setting in settings:
        if setting['original_key'] != "" and setting['hot_key'] != "":
            hook = remap_key(setting['original_key'], setting['hot_key'], setting['app'], settings)
            hooks.append(hook)

    try:
        while not stop_event.is_set():
            time.sleep(0.1)  # 短時間待機して停止フラグをチェック
    except KeyboardInterrupt:
        pass
    finally:
        for hook in hooks:
            keyboard.unhook(hook)
        print("Stopped key transformer.")
    
#####################################################################################
#####################################################################################
# 状態ファイル
STATE_FILE = "state.json"

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

# グローバル変数としてスレッドを管理
key_transformer_thread = None
is_transformer_running = load_state().get("is_running", False)

#####################################################################################
#####################################################################################
THREAD_ID_FILE = "thread_id.txt"

def start_key_transformer():
    global key_transformer_thread, is_transformer_running
    if key_transformer_thread is None or not key_transformer_thread.is_alive():
        stop_event.clear()  # 停止リクエストをクリア
        key_transformer_thread = threading.Thread(target=key_transformer, name="KeyTransformerThread")
        key_transformer_thread.start()
        is_transformer_running = True
        save_state({"is_running": is_transformer_running})
        print("Key transformer started.")
        print(threading.enumerate())

def stop_key_transformer():
    global key_transformer_thread, is_transformer_running
    for thread in threading.enumerate():
        if thread.name == "KeyTransformerThread":
            stop_event.set()  # 停止リクエストを設定
            thread.join()  # スレッドが終了するまで待つ
            key_transformer_thread = None
            is_transformer_running = False
            save_state({"is_running": is_transformer_running})
            print("Key transformer stopped.")
            return
    print(threading.enumerate())
    print("Key transformer thread not found.")
#####################################################################################
#####################################################################################


def main(page):
    global p
    p = page
    page.title = "Flexkey"
    # ウィンドウを閉じるときの動作を設定
    
    # page.window_prevent_close = True
    # page.window_title_bar_hidden =True
    page.window_width = 500  # 初期ウィンドウの幅を設定
    page.window_height = 600  # 初期ウィンドウの高さを設定

    stop_key_transformer()
    
    dropdown = ft.Dropdown(label="Open Applications", options=[])
    
    visible_windows = get_win_info.get_open_windows()
    for process_name in visible_windows:
        dropdown.options.append(ft.dropdown.Option(text=f"{process_name}",key=f"{process_name}"))

    # 表のヘッダーを定義
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Original Key")),
            ft.DataColumn(ft.Text("Hot Key")),
            ft.DataColumn(ft.Text("-"))
        ],
        rows=[]
    )

    current_key_input = None

    def on_change(e):
        # 設定ファイルを読み込む
        settings = load_settings('settings.json')
        selected_app = dropdown.value
        new_rows = []
        for setting in settings:
            if setting['original_key'] == "":
                text_original_key = "set original key"
            else:
                text_original_key = setting['original_key']

            if setting['hot_key'] == "":
                text_hot_key = "set hot key"
            else:
                text_hot_key = setting['hot_key']
            if setting['app'] == selected_app:
                new_rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.TextButton(text=text_original_key, on_click=lambda e, uid=setting['uid'], key="original_key": open_dialog(uid, key))),
                        ft.DataCell(ft.TextButton(text=text_hot_key, on_click=lambda e, uid=setting['uid'], key="hot_key": open_dialog(uid, key))),
                        ft.DataCell(ft.TextButton(text="Delete", on_click=lambda e, s=setting: delete_row(s['uid']), style=ft.ButtonStyle(color="red")))
                    ])
                )
        table.rows = new_rows
        page.update()  # UIを更新

    # 新しい行を追加する関数
    def add_row(e):
        selected_app = dropdown.value
        if selected_app:
            new_uid = str(uuid.uuid4())
            new_row = {
                "uid": new_uid,
                "app": selected_app,
                "original_key": "",
                "hot_key": ""
            }
            settings = load_settings('settings.json')
            settings.append(new_row)
            save_settings('settings.json', settings)

            table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.TextButton(text="set original key", on_click=lambda e, uid=new_uid, key="original_key": open_dialog(uid, key))),
                    ft.DataCell(ft.TextButton(text="set hot key", on_click=lambda e, uid=new_uid, key="hot_key": open_dialog(uid, key))),
                    ft.DataCell(ft.TextButton(text="Delete", on_click=lambda e: delete_row(new_uid), style=ft.ButtonStyle(color="red")))
                ])
            )
            page.update()  # UIを更新
    # 行を削除する関数
    def delete_row(uid):
        try:
            settings = load_settings('settings.json')
            settings = [setting for setting in settings if setting['uid'] != uid]
            save_settings('settings.json', settings)
            update_table()  # Refresh the table
        except Exception as e:
            print(f"Error deleting row: {e}")

    # キー設定のダイアログ
    def open_dialog(uid, key):
        nonlocal current_key_input
        settings = load_settings('settings.json')
        selected_row = next(setting for setting in settings if setting['uid'] == uid)
        current_value = selected_row[key]
        key_input = ft.TextField(label=f"Set {key.replace('_', ' ').title()}",value=current_value,hint_text="Press key")
        current_key_input = key_input
        hotkeys = []
        modifiers = {"shift", "ctrl", "alt", "windows"}

        if key == "original_key":

            def on_key(event):
                if current_key_input is not None:
                    current_key_input.value = event.name
                    page.update()

            keyboard.hook(on_key)
        else:
            

            def on_key(event):
                if current_key_input is not None:
                    if event.event_type == "down":
                        key_name = event.name
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
                    current_key_input.value = hotkey
                    page.update()

            keyboard.hook(on_key)
        
        def save_key(event):
            new_key = key_input.value
            if (key == "original_key" and is_valid_key(new_key)) or (key == "hot_key" and is_valid_hotkey(new_key)):
                selected_row[key] = new_key
                save_settings('settings.json', settings)
                dlg.open = False
                update_table()
            else:
                error_message.value = "Invalid key. Please enter a valid key."
                page.update()

        def reset_dlg(e):
            current_key_input.value = ""
            hotkeys.clear()
            page.update()
            
        def close_dlg(e):
            page.dialog = dlg
            dlg.open = False
            page.update()

        
        save_button = ft.TextButton("Save", on_click=save_key)
        cancel_button = ft.TextButton("Cancel", on_click=close_dlg)
        reset_button = ft.TextButton("Reset", on_click=reset_dlg)
        error_message = ft.Text(value="", color="red")

        dlg = ft.AlertDialog(
            content=ft.Container(
                content=ft.Column([
                    key_input, 
                    error_message, 
                    ft.Container(
                        content=ft.Row(
                            [cancel_button, reset_button, save_button], 
                            alignment=ft.MainAxisAlignment.SPACE_EVENLY
                        ),
                        padding=ft.padding.only(top=10)
                    )
                ], tight=True),
                border_radius=5,
                padding=ft.padding.all(10),
                alignment=ft.alignment.center,
                height=140
            )
        )

        page.dialog = dlg
        dlg.open=True
        page.update()

    # テーブルを更新する関数
    def update_table():
        settings = load_settings('settings.json')
        selected_app = dropdown.value
        new_rows = []
        for setting in settings:
            if setting['app'] == selected_app:
                if setting['original_key'] == "":
                    text_original_key = "set original key"
                else:
                    text_original_key = setting['original_key']

                if setting['hot_key'] == "":
                    text_hot_key = "set hot key"
                else:
                    text_hot_key = setting['hot_key']
                new_rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.TextButton(text=text_original_key, on_click=lambda e, s=setting: open_dialog(s['uid'], "original_key"))),
                        ft.DataCell(ft.TextButton(text=text_hot_key, on_click=lambda e, s=setting: open_dialog(s['uid'], "hot_key"))),
                        ft.DataCell(ft.TextButton(text="Delete", on_click=lambda e, s=setting: delete_row(s['uid']), style=ft.ButtonStyle(color="red")))
                    ])
                )
        table.rows = new_rows
        page.update()


    dropdown.on_change = on_change
    #ハンバーガーメニューの作成
    menu = ft.PopupMenuButton(
        items=[
            ft.PopupMenuItem(text="Enable Key Transformation", on_click=lambda e: start_key_transformer()),
            ft.PopupMenuItem(text="Disable Key Transformation", on_click=lambda e: stop_key_transformer())
        ]
    )

    def on_segment_change(e):
        if e.control.selected_index==0:
            start_key_transformer()
        else:
            stop_key_transformer()

    dropdown.on_change = on_change
    

    init_selected_index = 1

    if is_transformer_running is True:
        init_selected_index = 0
        
    # CupertinoSlidingSegmentedButtonの作成
    segmented_control = ft.CupertinoSlidingSegmentedButton(
        selected_index=init_selected_index,
        controls=[
                ft.Text("On"),
                ft.Text("Off")
            ],
        on_change=on_segment_change
    )
    # +ボタンを作成して新しい行を追加する
    add_row_button = ft.FloatingActionButton(icon=ft.icons.ADD, on_click=add_row)

    scrollable_table = ft.Column([table], scroll=ft.ScrollMode.AUTO, expand=True)

    page.add(segmented_control,dropdown, scrollable_table, add_row_button)


ft.app(target=main)
