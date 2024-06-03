import psutil
import pygetwindow as gw
import ctypes
import ctypes.wintypes


# Win32 API を使用してウィンドウハンドルからプロセスIDを取得する関数
def get_process_id_from_hwnd(hwnd):
    try:
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value
    except Exception as e:
        print(f"Error getting process ID: {e}")
    return None

# アクティブなウィンドウのプロセス名を取得
def get_active_process_name():
    try:
        window = gw.getActiveWindow()
        if window:
            hwnd = window._hWnd
            pid = get_process_id_from_hwnd(hwnd)
            if pid:
                process = psutil.Process(pid)
                return process.name()
    except Exception as e:
        print(f"Error getting active process name: {e}")
    return None

# 開いているすべてのウィンドウのプロセス名を取得
def get_open_windows():
    open_windows = []
    try:
        windows = gw.getAllTitles()
        for window_title in windows:
            if window_title:
                window = gw.getWindowsWithTitle(window_title)[0]
                hwnd = window._hWnd
                pid = get_process_id_from_hwnd(hwnd)

                if pid:
                    process = psutil.Process(pid)
                    open_windows.append(process.name())

    except Exception as e:
        print(f"Error getting open windows: {e}")
    return open_windows

