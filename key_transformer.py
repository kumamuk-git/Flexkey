import json
import keyboard
import get_win_info

# JSONファイルを読み込む関数
def load_settings(filename):
    with open(filename, 'r') as file:
        return json.load(file)
    
def remap_key(src, dst, active_process, settings):
    def handler(event):
        if event.event_type == keyboard.KEY_DOWN:
            if get_win_info.get_active_process_name() == active_process:
                keyboard.press_and_release(dst)
                return False  # キーイベントをキャンセルしてホットキーを送信
        return True  # それ以外の場合はキーイベントをキャンセルしない
    return keyboard.hook_key(src, handler, suppress=True)


# メインロジック
def main():
    settings = load_settings('settings.json')
    # 各キーを設定
    hooks = []
    for setting in settings:
        if setting['original_key'] != "" and setting['hot_key'] != "":
            hook = remap_key(setting['original_key'], setting['hot_key'], setting['app'], settings)
            hooks.append(hook)

    try:
        keyboard.wait()  # メインスレッドを維持するために待機
    except KeyboardInterrupt:
        pass
    finally:
        # 終了時にフックを解除
        for hook in hooks:
            keyboard.unhook(hook)

if __name__ == "__main__":
    main()
    