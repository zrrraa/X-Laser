#include "MyTFTLCD.h"

#define USE_UI     // if you want to use the ui export from Squareline ,pleease define USE_UI.
#define Display_28 // according to the board you using ,if you using the ESP32 Display 3.5inch board, please define 'Display_35'.if using 2.4inch board,please define 'Display_24'.

#ifdef USE_UI
#include <lvgl.h>
#include "ui.h"
#endif

#if defined Display_35 // ESP32 Display 3.5inch Board
/*screen resolution*/
static const uint16_t screenWidth = 480;
static const uint16_t screenHeight = 320;
uint16_t calData[5] = {353, 3568, 269, 3491, 7}; /*touch caldata*/

#elif defined Display_24 // ESP32 Display 2.4inch Board
static const uint16_t screenWidth = 320;
static const uint16_t screenHeight = 240;
uint16_t calData[5] = {557, 3263, 369, 3493, 3};

#elif defined Display_28 // ESP32 Display 2.8inch Board
static const uint16_t screenWidth = 320;
static const uint16_t screenHeight = 240;
uint16_t calData[5] = {189, 3416, 359, 3439, 1};
#endif

TFT_eSPI lcd = TFT_eSPI(); /* TFT entity */

#if defined USE_UI
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf1[screenWidth * screenHeight / 13];

// declare
void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p);
void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data);

void lcd_init()
{
  lcd.begin();
  lcd.setRotation(3);
  lcd.fillScreen(TFT_BLACK);
  lcd.setTouch(calData);
  delay(100);

#if defined USE_UI
  // lvgl init
  lv_init();

  lv_disp_draw_buf_init(&draw_buf, buf1, NULL, screenWidth * screenHeight / 13);

  /*Display init*/
  static lv_disp_drv_t disp_drv;
  lv_disp_drv_init(&disp_drv);
  /*Display driver port of LVGL*/
  disp_drv.hor_res = screenWidth;
  disp_drv.ver_res = screenHeight;
  disp_drv.flush_cb = my_disp_flush;
  disp_drv.draw_buf = &draw_buf;
  lv_disp_drv_register(&disp_drv);

  /*touch driver port of LVGL*/
  static lv_indev_drv_t indev_drv;
  lv_indev_drv_init(&indev_drv);
  indev_drv.type = LV_INDEV_TYPE_POINTER;
  indev_drv.read_cb = my_touchpad_read;
  lv_indev_drv_register(&indev_drv);

  ui_init(); // LVGL UI init

#else // if you haven't defined 'USE_UI', the program compiler will not compile the code above; it will just compile the code follows

  lcd.fillScreen(TFT_BLACK); // The screen of the board will change the screen color per second.
  delay(1000);
  lcd.fillScreen(TFT_WHITE);
  delay(1000);
  lcd.fillScreen(TFT_RED);
  delay(1000);
  lcd.fillScreen(TFT_YELLOW);
  delay(1000);
  lcd.fillScreen(TFT_BLUE);
  delay(1000);
  lcd.fillScreen(TFT_GREEN);
  delay(1000);
#endif

  xTaskCreatePinnedToCore(
      myTFTLCDLoop, /* Task function. */
      "TFTLCD",     /* name of task. */
      4096,         /* Stack size of task */
      NULL,         /* parameter of the task */
      3,            /* priority of the task */
      NULL,         /* Task handle to keep track of created task */
      1);           /* pin task to core 1 */

  Serial.println("TFTLCD Setup done");
}

void lcd_loop()
{
#if defined USE_UI
  lv_timer_handler();
  delay(5);
#else
  while (1)
    ;
#endif
}

void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p)
{
  uint32_t w = (area->x2 - area->x1 + 1);
  uint32_t h = (area->y2 - area->y1 + 1);

  lcd.startWrite();
  lcd.setAddrWindow(area->x1, area->y1, w, h);
  lcd.pushColors((uint16_t *)&color_p->full, w * h, true);
  lcd.endWrite();

  lv_disp_flush_ready(disp);
}

uint16_t touchX, touchY;
/*touch read*/
void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data)
{

  bool touched = lcd.getTouch(&touchX, &touchY, 600);
  if (!touched)
  {
    data->state = LV_INDEV_STATE_REL;
  }
  else
  {
    data->state = LV_INDEV_STATE_PR;

    /*set location*/
    data->point.x = touchX;
    data->point.y = touchY;

    Serial.print("Data x ");
    Serial.println(touchX);

    Serial.print("Data y ");
    Serial.println(touchY);
  }
}
#endif
