#ifndef H_SPIRENDERER_H
#define H_SPIRENDERER_H

#include "main.h"

#include "ArduinoJson.h"
#include "driver/spi_master.h"
#include <esp_attr.h>
#include <vector>

#define PIN_NUM_MISO -1
#define PIN_NUM_MOSI 25
#define PIN_NUM_CLK 26
#define PIN_NUM_CS 27
#define PIN_NUM_LDAC 33
#define PIN_NUM_LASER_R 13
#define PIN_NUM_LASER_G 16
#define PIN_NUM_LASER_B 17

#define MAXRECORDS 3000

typedef struct spi_device_t *spi_device_handle_t; ///< Handle for a device on a SPI bus

class SPIRenderer
{
private:
    spi_device_handle_t spi;
    volatile int draw_position;
    volatile int frame_position;

public:
    SPIRenderer();
    void IRAM_ATTR draw();
    void start();
};

extern int curMedia;
extern const int bufferFrames;
extern JsonArray avaliableMedia;
extern volatile bool TFTLCD_status;
extern TaskHandle_t drawTaskHandle;
extern int LaserBegin;

void setupRenderer();
void draw_task();
void nextMedia(int position);

#endif /* H_SPIRENDERER_H */