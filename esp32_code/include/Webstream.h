#ifndef H_WEBSTREAM_H
#define H_WEBSTREAM_H

#include "main.h"

#include <Wifi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <AsyncElegantOTA.h>

void handleWebSocketMessage(void *arg, uint8_t *data, size_t len);
void onWsEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len);
void handleStream(uint8_t *data, size_t len, int index, int totalLen);
void web_init();

#define bufferLen 6

#endif