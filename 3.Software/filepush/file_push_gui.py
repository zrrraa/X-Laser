import serial
import serial.tools.list_ports
import threading
import time
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext

class SerialFileSender:
    def __init__(self, root):
        self.root = root
        self.root.title("X-Laser上位机")
        self.root.geometry("600x450")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 串口配置
        self.serial_port = None
        self.available_ports = []
        self.stop_thread = False
        self.lock = threading.Lock()

        # 创建界面元素
        self.create_widgets()

        # 启动串口检测线程
        self.port_check_thread = threading.Thread(target=self.update_ports)
        self.port_check_thread.daemon = True
        self.port_check_thread.start()

        # 启动串口读取线程
        self.reader_thread = threading.Thread(target=self.read_serial_output)
        self.reader_thread.daemon = True
        self.reader_thread.start()

    def create_widgets(self):
        # 串口选择
        self.port_frame = tk.Frame(self.root)
        self.port_frame.pack(pady=10)

        tk.Label(self.port_frame, text="选择串口:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combobox = ttk.Combobox(self.port_frame, textvariable=self.port_var, width=20)
        self.port_combobox.pack(side=tk.LEFT, padx=5)

        # 文件选择
        self.file_frame = tk.Frame(self.root)
        self.file_frame.pack(pady=5)

        self.file_var = tk.StringVar()
        tk.Entry(self.file_frame, textvariable=self.file_var, width=40, state='readonly').pack(side=tk.LEFT)
        tk.Button(self.file_frame, text="选择文件", command=self.select_file).pack(side=tk.LEFT, padx=5)

        # 操作按钮
        self.btn_frame = tk.Frame(self.root)
        self.btn_frame.pack(pady=10)
        self.send_btn = tk.Button(self.btn_frame, text="发送文件", command=self.start_send)
        self.send_btn.pack(side=tk.LEFT, padx=10)
        self.clear_btn = tk.Button(self.btn_frame, text="清空日志", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT)

        # 日志显示
        self.log_frame = tk.LabelFrame(self.root, text="传输日志")
        self.log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=15, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_ports(self):
        while not self.stop_thread:
            ports = serial.tools.list_ports.comports()
            port_list = [f"{p.device} ({p.description.split(' ')[0]})" for p in ports]
            
            if port_list != self.available_ports:
                self.available_ports = port_list
                self.port_combobox['values'] = self.available_ports
                if self.available_ports:
                    self.port_combobox.current(0)
            
            time.sleep(1)

    def select_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_var.set(file_path)

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def read_serial_output(self):
        while not self.stop_thread:
            if self.serial_port and self.serial_port.is_open and self.serial_port.in_waiting > 0:
                with self.lock:
                    try:
                        output = self.serial_port.readline().decode(errors='ignore').strip()
                        if output:
                            self.root.after(0, self.log_message, f"ESP32 >> {output}")
                    except Exception as e:
                        self.root.after(0, self.log_message, f"读取错误: {str(e)}")
            time.sleep(0.01)

    def start_send(self):
        if not self.file_var.get():
            messagebox.showwarning("错误", "请选择要发送的文件")
            return

        selected_port = self.port_var.get().split(' ')[0]
        if not selected_port:
            messagebox.showwarning("错误", "请选择有效的串口")
            return

        # 尝试打开串口
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.serial_port = serial.Serial(selected_port, 1000000, timeout=1)
            time.sleep(0.5)
            self.status_var.set(f"已连接到 {selected_port}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开串口: {str(e)}")
            return

        # 禁用按钮
        self.send_btn.config(state=tk.DISABLED)
        self.log_message(f"开始传输文件: {self.file_var.get()}")

        # 启动发送线程
        send_thread = threading.Thread(target=self.send_file, args=(self.file_var.get(),))
        send_thread.daemon = True
        send_thread.start()

    def send_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                # 发送文件头
                header = f"FILENAME:{file_name}:{file_size}:"
                self.log_message(f"发送文件头: {header.strip()}")
                
                with self.lock:
                    self.serial_port.write(header.encode())
                
                # 等待ESP32就绪
                time.sleep(0.5)
                if self.serial_port.in_waiting > 0:
                    with self.lock:
                        response = self.serial_port.readline().decode().strip()
                    if "READY" not in response:
                        self.log_message(f"设备未就绪: {response}")
                        self.serial_port.close()
                        self.send_btn.config(state=tk.NORMAL)
                        return
                
                # 发送文件内容
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    with self.lock:
                        self.serial_port.write(chunk)
                    time.sleep(0.01)  # 防止缓冲区溢出
                
                self.log_message("文件传输完成")
        
        except Exception as e:
            self.log_message(f"传输失败: {str(e)}")
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.send_btn.config(state=tk.NORMAL)
            self.status_var.set("就绪")

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def on_close(self):
        self.stop_thread = True
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialFileSender(root)
    root.mainloop()