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
extern TFT_eSPI lcd;

extern uint16_t X_Position;
extern uint16_t Y_Position;
extern uint16_t X_Position_Old;
extern uint16_t Y_Position_Old;

#endif /* H_MYTFTLCD_H */