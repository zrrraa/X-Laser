#ifndef H_MYTFTLCD_H
#define H_MYTFTLCD_H

#include "main.h"

#include "TFT_eSPI.h"
#include <SPI.h>
#include <lvgl.h>
#include "ui.h"

#include "FS.h"
#include "SPIFFS.h"

extern fs::SPIFFSFS SPIFFS;
#define CALIBRATION_FILE "/TouchCalData3"
#define REPEAT_CAL false // false则使用之前的校准文件, true则重新校准

void lcd_init();
void lcd_loop();

void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p);
void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data);
void touch_calibrate();

extern TaskHandle_t myTFTLCDHandle;
extern TFT_eSPI tft;

extern uint16_t X_Position;
extern uint16_t Y_Position;
extern uint16_t X_Position_Old;
extern uint16_t Y_Position_Old;

#endif /* H_MYTFTLCD_H */