#include "FilePush.h"

File push_file;
bool receiving = false;
String push_header;
uint32_t file_size;
uint32_t received_size = 0;

bool filePushFlag = false; // 用于标记是否接收到文件

unsigned long timeDog4 = 0;

File pushroot;

TaskHandle_t FilePushHandle;

void setupFilePush()
{
    Serial.println("FilePush Setup");
    Serial.println("Initializing SD card...");
    if (!SD_MMC.begin("/sdcard", true))
    {
        Serial.println("Card Mount Failed");
        return;
    }
    Serial.println("SD card initialized.");

    Serial.println("Ready to receive files.");

    // xTaskCreatePinnedToCore(
    //     loopFilePush,    /* Task function. */
    //     "loopFilePush",  /* name of task. */
    //     4096,            /* Stack size of task */
    //     NULL,            /* parameter of the task */
    //     3,               /* priority of the task */
    //     &FilePushHandle, /* Task handle to keep track of created task */
    //     0);              /* pin task to core 0 */
    Serial.println("loopFilePush Setup");
}

void loopFilePush()
{
    if (Serial.available())
    {
        if (!receiving)
        {
            Pause_Flag = 1; // 暂停缓存
            delay(100);
            avaliableMedia.clear(); // 清空文件列表
            digitalWrite(PIN_NUM_LASER_R, HIGH);
            digitalWrite(PIN_NUM_LASER_G, HIGH);
            digitalWrite(PIN_NUM_LASER_B, HIGH);
            clearFilePushFolder();
            for (int i = 0; i < bufferFrames; i++)
            {
                ilda->frames[i].isBuffered = false;
            }

            // 解析文件头信息
            push_header = Serial.readStringUntil(':');
            if (push_header.startsWith("FILENAME"))
            {
                String file_name = Serial.readStringUntil(':');
                file_name = "/FilePush/" + file_name;
                file_size = Serial.readStringUntil(':').toInt();

                // 创建新文件
                Serial.printf("接收文件: %s, 大小: %d bytes\n", file_name.c_str(), file_size);
                push_file = SD_MMC.open(file_name.c_str(), FILE_WRITE);
                if (push_file)
                {
                    receiving = true;
                    received_size = 0;
                    Serial.println("READY"); // 发送就绪信号
                }
                else
                {
                    Serial.println("文件创建失败");
                }
            }
        }
        else
        {
            // 接收文件内容
            uint8_t buffer[FILE_BUFFER_SIZE];
            int bytes_read = Serial.readBytes(buffer, FILE_BUFFER_SIZE);

            if (bytes_read > 0)
            {
                push_file.write(buffer, bytes_read);
                received_size += bytes_read;

                // 检查是否接收完成
                if (received_size >= file_size)
                {
                    push_file.close();
                    receiving = false;
                    Serial.println("接收完成");

                    RenderPushFile();
                }
            }
        }
    }
}

void RenderPushFile()
{
    pushroot = SD_MMC.open("/FilePush");
    while (true)
    {
        File entry = pushroot.openNextFile();
        if (!entry)
        {
            break;
        }
        if (!entry.isDirectory() && String(entry.name()).indexOf(".ild") != -1)
        {
            Serial.println(entry.name());
            avaliableMedia.add(String(entry.name()));
        }
    }

    if (avaliableMedia.size() == 0)
    {
        Serial.println("Error: No valid .ild files found in /FilePush");
        return;
    }

    nextMedia(1); // 播放刚刚接收的文件
    Pause_Flag = 0;
}

void clearFilePushFolder()
{
    // 打开 FilePush 文件夹
    File root = SD_MMC.open("/FilePush");
    if (!root)
    {
        Serial.println("FilePush folder does not exist. Creating...");
        // 如果文件夹不存在，创建它
        if (!SD_MMC.mkdir("/FilePush"))
        {
            Serial.println("Failed to create FilePush folder.");
            return;
        }
        return; // 文件夹刚刚创建，无需清空
    }

    // 遍历文件夹中的文件并删除
    File file = root.openNextFile();
    while (file)
    {
        String fileName = file.name();
        Serial.print("Deleting file: ");
        Serial.println(fileName);
        fileName = "/FilePush/" + fileName;

        // 删除文件
        if (!SD_MMC.remove(fileName.c_str()))
        {
            Serial.print("Failed to delete file: ");
            Serial.println(fileName);
        }

        file.close();
        file = root.openNextFile();
    }

    root.close();
    Serial.println("FilePush folder cleared.");
}
