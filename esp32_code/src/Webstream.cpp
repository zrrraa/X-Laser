#include "Webstream.h"

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

int loadedLen = 0;

// Current ILDA Buffer  当前的ILDA内存，采用Buffer的形式，为了能更快的加载大型ILDA文件。动态读取文件，申请内存，避免一下子把整个ILDA文件的所有帧的内存都申请了（没有那么多PSRAM）
uint8_t chunkTemp[64];
int tempLen = 0;

void handleWebSocketMessage(void *arg, uint8_t *data, size_t len)
{
    AwsFrameInfo *info = (AwsFrameInfo *)arg;
    // 单帧
    if (info->final && info->index == 0 && info->len == len)
    {
        handleStream(data, len, 0, info->len);
    }
    // 多帧
    else
    {
        if (info->index == 0)
        {
            // if (info->num == 0)
            // Serial.println("MSG Start");
            // Serial.println("Frame Start");
            // handleStream(data, len, 0, info->len);
        }
        // Serial.print(info->index);
        // Serial.print(" ");
        // Serial.println(len);
        if ((info->index + len) == info->len)
        {
            // Serial.println("Frame End");
            if (info->final)
            {
                // Serial.println("MSG End");
                // Serial.println(frameLen);
                handleStream(data, len, info->index, info->len);
            }
        }
        else
        {
            handleStream(data, len, info->index, info->len);
        }
    }
}

void onWsEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len)
{
    if (type == WS_EVT_CONNECT)
    {
        // client connected
        ESP_LOGI("ws[%s][%u] connect\n", server->url(), client->id());
        // client->printf("I am bbLaser :)", client->id());
        // client->ping();
        isStreaming = true;
    }
    else if (type == WS_EVT_DISCONNECT)
    {
        // client disconnecteds
        ESP_LOGI("ws[%s][%u] disconnect: %u\n", server->url(), client->id());
        isStreaming = false;
    }
    else if (type == WS_EVT_DATA)
    {
        handleWebSocketMessage(arg, data, len);
    }
}

bool ILDAFile::parseStream(uint8_t *data, size_t len, int frameIndex, int totalLen)
{
    if (frames[cur_buffer].isBuffered == false)
    {
        // frames[cur_buffer].isBuffered = true;
        frames[cur_buffer].number_records = totalLen / bufferLen;
        ILDA_Record_t *records = frames[cur_buffer].records;

        /*
         Serial.print("Len: ");
         Serial.println(len);
         Serial.print("Get Frame: ");

         Serial.print(frameIndex);
         Serial.print(" / ");
         Serial.print(totalLen);
         Serial.print("  ");
         Serial.println(cur_buffer);
         */

        for (size_t i = 0; i < len / bufferLen; i++)
        {
            int16_t x = (data[i * bufferLen] << 8) | data[i * bufferLen + 1];
            int16_t y = (data[i * bufferLen + 2] << 8) | data[i * bufferLen + 3];

            /*
            Serial.print(frameIndex/bufferLen + i);
            Serial.print(",");
            Serial.print(x);
            Serial.print(",");
            Serial.println(y);
            */
            /*
            Serial.print(",");
            Serial.print(data[i*bufferLen+4]);
            Serial.print(",");
            Serial.println(data[i*bufferLen+5]);
            Serial.println((data[i*bufferLen+5] & 0b01000000) == 0);*/

            records[frameIndex / bufferLen + i].x = x;
            records[frameIndex / bufferLen + i].y = y;
            records[frameIndex / bufferLen + i].z = 0;
            records[frameIndex / bufferLen + i].color = data[i * bufferLen + 4];
            records[frameIndex / bufferLen + i].status_code = data[i * bufferLen + 5];
        }
        loadedLen += len;

        if (loadedLen >= totalLen)
        {
            // Serial.println("Frame End");
            loadedLen = 0;
            cur_buffer++;
            if (cur_buffer > bufferFrames - 1)
                cur_buffer = 0;

            cur_frame++;
            // Serial.println(cur_frame);
            if (cur_frame > file_frames - 1)
            {
                cur_frame = 0;
            }
        }

        return true;
    }
    else
        return false; // This frame has been buffered and not display yet.. 该帧已缓存且未Render，可能是读文件、串流太快了？忽视掉就好 0w0
}

void handleStream(uint8_t *data, size_t len, int index, int totalLen)
{
    // Serial.println("Stream");
    int newtempLen = (tempLen + len) % 6;
    // Serial.print("newTemp:");
    // Serial.println(newtempLen);
    if (tempLen > 0)
    {
        // memcpy(chunkTemp+tempLen, data, len - newtempLen);
        uint8_t concatData[len - newtempLen + tempLen];
        memcpy(concatData, chunkTemp, tempLen);
        memcpy(concatData + tempLen, data, len - newtempLen); // copy the address
        // Serial.print("Temp Concat Len: ");
        // Serial.println(len-newtempLen+tempLen);
        ilda->parseStream(concatData, len - newtempLen + tempLen, index - tempLen, totalLen);
    }
    else
    {
        // Serial.print("No Concat Len: ");
        // Serial.println(len-newtempLen+tempLen);
        ilda->parseStream(data, len - newtempLen, index, totalLen);
    }
    for (size_t i = 0; i < newtempLen; i++)
    {
        chunkTemp[i] = data[len - newtempLen + i];
    }
    tempLen = newtempLen;
}

void web_init()
{
    WiFi.begin("zrrraa", "zhongrui");
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request)
              { request->redirect("http://bblaser.bbrealm.com/?ip=" + WiFi.localIP().toString()); });
    AsyncElegantOTA.begin(&server); // Start ElegantOTA
    // attach AsyncWebSocket
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    DefaultHeaders::Instance().addHeader("Access-Control-Allow-Origin", "*");
    server.begin();
}