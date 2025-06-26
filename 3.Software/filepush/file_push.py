import serial
import time
import os
import threading

# 配置串口参数
ser = serial.Serial('COM10', 921600, timeout=1)
time.sleep(2)  # 等待串口初始化

# 线程控制标志和锁
stop_thread = False
lock = threading.Lock()

def read_serial_output():
    """持续读取ESP32的串口输出，支持优雅退出"""
    global stop_thread
    while not stop_thread:
        if ser.is_open and ser.in_waiting > 0:
            with lock:
                output = ser.readline().decode(errors='ignore').strip()
                if output:
                    print(f"ESP32 >> {output}")
        else:
            time.sleep(0.01)

def send_file(file_path):
    """发送文件到ESP32"""
    try:
        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 发送文件头
            header = f"FILENAME:{file_name}:{file_size}:"
            print(f"发送文件头: {header.strip()}")
            
            with lock:
                ser.write(header.encode())
            
            # 等待ESP32就绪
            time.sleep(0.5)
            if ser.in_waiting > 0:
                with lock:
                    response = ser.readline().decode().strip()
                if "READY" not in response:
                    print(f"设备未就绪: {response}")
                    return
            
            # 发送文件内容
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                with lock:
                    ser.write(chunk)
                time.sleep(0.01)  # 防止缓冲区溢出
            
            print("文件传输完成")

    except Exception as e:
        print(f"传输失败: {e}")

if __name__ == "__main__":
    # 启动串口读取线程（守护模式）
    reader_thread = threading.Thread(target=read_serial_output)
    reader_thread.daemon = True
    reader_thread.start()
    
    try:
        while True:
            print("\n1: 发送文件；2: 退出程序")
            choice = input("请输入选项（1/2）：").strip()
            
            if choice == '1':
                send_file("aristcat.ild")
            elif choice == '2':
                print("正在关闭程序...")
                stop_thread = True
                reader_thread.join(timeout=2)  # 等待线程结束
                if ser.is_open:
                    ser.close()
                    print("串口已关闭")
                break
            else:
                print("无效选项，请重新输入！")
    
    except KeyboardInterrupt:
        print("\n强制退出程序")
        stop_thread = True
        if ser.is_open:
            ser.close()