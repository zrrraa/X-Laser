#include "MyTFTLCD.h"

static const uint16_t screenWidth = 480;
static const uint16_t screenHeight = 320;

static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[screenWidth * screenHeight / 10];

// 横屏显示，这里官方驱动没做好，要加参数的话应该是Height在前，不加参数可自适应
// TFT_eSPI tft = TFT_eSPI(screenWidth, screenHeight); /* TFT instance */
TFT_eSPI tft = TFT_eSPI(); /* TFT instance */

// 添加了自己校准触摸位置的代码
// uint16_t calData[5] = {296, 3630, 210, 3666, 1};

static const char *TAGLCD = "LCD";
TaskHandle_t myTFTLCDHandle;

uint16_t X_Position = 0;
uint16_t Y_Position = 0;
uint16_t X_Position_Old = 0;
uint16_t Y_Position_Old = 0;

/* Display flushing */
void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p)
{
  uint32_t w = (area->x2 - area->x1 + 1);
  uint32_t h = (area->y2 - area->y1 + 1);

  tft.startWrite();
  tft.setAddrWindow(area->x1, area->y1, w, h);
  tft.pushColors((uint16_t *)&color_p->full, w * h, true);
  tft.endWrite();

  lv_disp_flush_ready(disp);
}

/*Read the touchpad*/
void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data)
{
  uint16_t touchX = 0, touchY = 0;

  bool touched = tft.getTouch(&touchX, &touchY, 600);

  if (!touched)
  {
    data->state = LV_INDEV_STATE_REL;
  }
  else
  {
    data->state = LV_INDEV_STATE_PR;

    /*Set the coordinates*/
    data->point.x = touchX;
    data->point.y = touchY;

    // Serial.print("Data x ");
    // Serial.println(touchX);

    // Serial.print("Data y ");
    // Serial.println(touchY);

    if (DrawNow_Flag == 1)
    {
      if (!((touchX >= 0 && touchX <= 125 && touchY >= 270 && touchY <= 320) || (touchX >= 0 && touchX <= 135 && touchY >= 0 && touchY <= 135) || (touchX >= 255 && touchX <= 480 && touchY >= 270 && touchY <= 320))) // 判定有效绘图范围
      {
        X_Position = touchX;
        Y_Position = touchY;
        if (X_Position != X_Position_Old || Y_Position != Y_Position_Old)
        {
          // 将这个像素点变白色，显示draw的轨迹
          // tft.drawPixel(X_Position, Y_Position, TFT_WHITE);
          tft.fillCircle(X_Position, Y_Position, 2, TFT_WHITE);

          // ESP_LOGI(TAGLCD, "DrawNow mode, notify the bufferloop!");
          xTaskNotifyGive(fileBufferHandle);
        }
      }
    }
  }
}

void lcd_init()
{
  lv_init();
  tft.begin();        /* TFT init */
  tft.setRotation(3); /* Landscape orientation, flipped */
  // tft.fillScreen(TFT_BLACK);
  touch_calibrate();
  // tft.setTouch(calData);
  delay(100);
  lv_disp_draw_buf_init(&draw_buf, buf, NULL, screenWidth * screenHeight / 10);

  /*Initialize the display*/
  static lv_disp_drv_t disp_drv;
  lv_disp_drv_init(&disp_drv);
  /*Change the following line to your display resolution*/
  disp_drv.hor_res = screenWidth;
  disp_drv.ver_res = screenHeight;
  disp_drv.flush_cb = my_disp_flush;
  disp_drv.draw_buf = &draw_buf;
  lv_disp_drv_register(&disp_drv);

  /*Initialize the (dummy) input device driver*/
  static lv_indev_drv_t indev_drv;
  lv_indev_drv_init(&indev_drv);
  indev_drv.type = LV_INDEV_TYPE_POINTER;
  indev_drv.read_cb = my_touchpad_read;
  lv_indev_drv_register(&indev_drv);

  ui_init();

  // 创建TFTLCD任务，用于处理LCD刷新和触摸，这个任务层级最低，在最开始就创建，且创建完成后马上进入阻塞状态
  xTaskCreatePinnedToCore(
      myTFTLCDLoop,     /* Task function. */
      "myTFTLCDHandle", /* name of task. */
      4096,             /* Stack size of task */
      NULL,             /* parameter of the task */
      3,                /* priority of the task */
      &myTFTLCDHandle,  /* Task handle to keep track of created task */
      0);               /* pin task to core 0 */

  ESP_LOGI(TAGLCD, "myTFTLCDLoop Setup");
  xTaskNotifyGive(myTFTLCDHandle);
  // delay(2000);
}

void lcd_loop()
{
  // int lv_timer = 0;
  // lv_timer = lv_timer_handler();
  // Serial.printf("wait %d for lv_timer_handler\r\n", lv_timer);
  // delay(lv_timer);

  // Serial.print("lcd_loop!");

  lv_timer_handler();
  delay(5);
}

void touch_calibrate()
{
  uint16_t calData[5];
  uint8_t calDataOK = 0;

  // check file system exists
  if (!SPIFFS.begin())
  {
    Serial.println("Formatting file system");
    SPIFFS.format();
    SPIFFS.begin();
  }

  // check if calibration file exists and size is correct
  if (SPIFFS.exists(CALIBRATION_FILE))
  {
    if (REPEAT_CAL)
    {
      // Delete if we want to re-calibrate
      SPIFFS.remove(CALIBRATION_FILE);
    }
    else
    {
      File f = SPIFFS.open(CALIBRATION_FILE, "r");
      if (f)
      {
        if (f.readBytes((char *)calData, 14) == 14)
          calDataOK = 1;
        f.close();
      }
    }
  }

  if (calDataOK && !REPEAT_CAL)
  {
    // calibration data valid
    tft.setTouch(calData);
  }
  else
  {
    // data not valid so recalibrate
    tft.fillScreen(TFT_BLACK);
    tft.setCursor(20, 0);
    tft.setTextFont(2);
    tft.setTextSize(1);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);

    tft.println("Touch corners as indicated");

    tft.setTextFont(1);
    tft.println();

    if (REPEAT_CAL)
    {
      tft.setTextColor(TFT_RED, TFT_BLACK);
      tft.println("Set REPEAT_CAL to false to stop this running again!");
    }

    tft.calibrateTouch(calData, TFT_MAGENTA, TFT_BLACK, 15);

    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.println("Calibration complete!");

    // store data
    File f = SPIFFS.open(CALIBRATION_FILE, "w");
    if (f)
    {
      f.write((const unsigned char *)calData, 14);
      f.close();
    }
    // Serial.println(calData[0]);
    // Serial.println(calData[1]);
    // Serial.println(calData[2]);
    // Serial.println(calData[3]);
    // Serial.println(calData[4]);
  }
}