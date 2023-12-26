#ifndef H_MYTFTLCD_H
#define H_MYTFTLCD_H

#include "main.h"

#include "TFT_eSPI.h"
#include <SPI.h>
#include <lvgl.h>
#include "ui.h"

void lcd_init();
void lcd_loop();

extern TaskHandle_t myTFTLCDHandle;

#endif /* H_MYTFTLCD_H */