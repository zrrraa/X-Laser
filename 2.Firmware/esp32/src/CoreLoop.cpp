#include "CoreLoop.h"

static const char *TAGCORE = "CORELOOP";

unsigned long timeDog = 0;
unsigned long timeDog2 = 0;
unsigned long timeDog3 = 0;

bool AutoPlay_Flag = 0;
bool Pause_Flag = 1;
bool DrawNow_Flag = 0;

char selected_text[32]; // Roller选中的文本缓冲区

// unsigned long LCD_freshPrevious = 0;
// unsigned long LCD_freshInterval = 1000 / 1000; // 1000Hz刷新LCD屏

// int kppsTime = 1000000 / (20 * 1000); // 20kHz
// volatile unsigned long timeOld;
// volatile unsigned long timeStart;

// 用于不断地将数据帧缓存到申请的三帧中去。一次fileBufferLoop会将一个数据帧的内容缓存到一个buffer中去
// fileBufferLoop执行的很快，不停的缓存，如果缓存满了则置于阻塞状态，投影出去，消耗了数据帧后会把它唤醒
// 在DrawNow模式下，每次循环只存储一个record，存储了即阻塞，LCD上画了新的点后唤醒
// 缓存优先于投影，将投影依赖于缓存。要停止投影，只需停止缓存
void fileBufferLoop(void *pvParameters)
{
  for (;;)
  {
    if (millis() - timeDog > 1000)
    {
      timeDog = millis();
      TIMERG0.wdt_wprotect = TIMG_WDT_WKEY_VALUE;
      TIMERG0.wdt_feed = 1;
      TIMERG0.wdt_wprotect = 0;
    }

    // 一切停止投影的状态
    // ESP_LOGI(TAGCORE, "Pause_Flag = %d", Pause_Flag);
    if (Pause_Flag == 1)
    {
      // ESP_LOGI(TAGCORE, "fileBufferLoop STOP");
      xTaskNotifyWait(0, 0, NULL, portMAX_DELAY);
    }

    // 缓存下一帧。如果缓存不成功，说明三帧都已经缓存了，则将fileBufferLoop置于阻塞状态
    if (!(ilda->tickNextFrame()))
    {
      // fileBufferLoop阻塞时可以开始运行TFTLCDLoop
      // TFTLCD_status = true;
      // ESP_LOGI(TAGCORE, "myTFTLCDLoop begin on core %d", xPortGetCoreID());
      // xTaskNotifyGive(myTFTLCDHandle);

      // ESP_LOGI(TAGCORE, "fileBufferLoop SLEEP on core %d", xPortGetCoreID());
      xTaskNotifyWait(0, 0, NULL, portMAX_DELAY);
    }
    else // 缓存成功了一帧
    {
      // ESP_LOGI(TAGCORE, "A frame has been buffered");
    }
  }
}

// 用于处理TFTLCD屏幕刷新与触摸的任务
// TFTLCD和SD共用一个SPI，如果并行会引起通信异常，具体表现为SD卡断开连接。这里用任务的阻塞与通知避免了两个任务同时运行
// 现采用SD_MMC通信，不再需要防并行处理
void myTFTLCDLoop(void *pvParameters)
{
  for (;;)
  {
    if (millis() - timeDog2 > 1000)
    {
      timeDog2 = millis();
      TIMERG0.wdt_wprotect = TIMG_WDT_WKEY_VALUE;
      TIMERG0.wdt_feed = 1;
      TIMERG0.wdt_wprotect = 0;
    }
    // if (TFTLCD_status == false) // 如果有已缓存且未投影的帧，fileBufferLoop要开始执行，TFTLCD必须阻塞状态等待
    // {
    //   ESP_LOGI(TAGCORE, "myTFTLCDLoop SLEEP");
    //   xTaskNotifyWait(0, 0, NULL, portMAX_DELAY);
    // }
    // else
    // {
    // ESP_LOGI(TAGCORE, "myTFTLCDLoop WORKING");

    lcd_loop();
    // }

    // TFTLCD按钮判断
    if (TFTLCD_BUTTON == 1)
    {
      // Test Point
      TFTLCD_BUTTON = 0;
      Pause_Flag = 1;
      delay(100);
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);

      // 先将Pause_Flag置0，否则缓存开始后立即停止
      AutoPlay_Flag = 0;
      Pause_Flag = 0;
      lv_roller_get_selected_str(ui_Roller1, selected_text, sizeof(selected_text));
      strcat(selected_text, ".ild");

      // 重置缓存帧的标记位，否则容易串流
      for (int i = 0; i < bufferFrames; i++)
      {
        ilda->frames[i].isBuffered = false;
      }

      for (uint16_t i = 0; i < avaliableMedia.size(); i++)
      {
        // Serial.println(selected_text);
        // Serial.println(avaliableMedia[i].as<String>().c_str());
        if (strcmp(selected_text, avaliableMedia[i].as<String>().c_str()) == 0)
        {
          Serial.print(selected_text);
          Serial.println(" begin!");

          nextMedia(i - curMedia);

          break;
        }
      }
    }
    else if (TFTLCD_BUTTON == 2) // AutoPlay
    {
      Serial.println("AutoPlay button");

      nextMedia(1);

      AutoPlay_Flag = 1;
      Pause_Flag = 0;
      TFTLCD_BUTTON = 0;
    }
    else if (TFTLCD_BUTTON == 3 || TFTLCD_BUTTON == 4) // Pause or goback screen
    {
      Serial.println("Pause or goback screen button");
      // 先阻止缓存，否则清空没用
      AutoPlay_Flag = 0;
      Pause_Flag = 1;
      TFTLCD_BUTTON = 0;

      // 缓存停止投影停止，RGB激光也要关闭
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);
    }
    else if (TFTLCD_BUTTON == 5) // Clear
    {
      Serial.println("Clear button");

      // 先阻止缓存，否则清空没用
      DrawNow_Flag = 1;
      Pause_Flag = 1;
      TFTLCD_BUTTON = 0;

      // RGB激光器关闭
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);
      ilda->frames[0].number_records = 0;
      DrawNow_records_position = 0; // 类似于栈操作，只重置了sp位置，但没有清空栈中的内容

      // 清除笔迹
      tft.fillRect(125, 270, 130, 50, TFT_BLACK);
      tft.fillRect(0, 135, 480, 138, TFT_BLACK);
      tft.fillRect(135, 0, 345, 135, TFT_BLACK);
    }
    else if (TFTLCD_BUTTON == 6) // Draw Now
    {
      Serial.println("Draw Now button");
      // 先清空，否则DrawNow_Flag置1后立即开始投影
      ilda->frames[0].number_records = 0;
      DrawNow_records_position = 0; // 类似于栈操作，只重置了sp位置，但没有清空栈中的内容

      DrawNow_Flag = 1;
      Pause_Flag = 0;
      TFTLCD_BUTTON = 0;
    }
    else if (TFTLCD_BUTTON == 7) // Goback screen
    {
      Serial.println("Goback screen button");
      // 先阻止缓存，否则清空没用
      DrawNow_Flag = 0;
      Pause_Flag = 1;
      TFTLCD_BUTTON = 0;

      // RGB激光器关闭
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);
      ilda->frames[0].number_records = 0;
      DrawNow_records_position = 0; // 类似于栈操作，只重置了sp位置，但没有清空栈中的内容
    }

    if (Pause_Flag == 1) // 保证激光器关闭
    {
      // RGB激光器关闭
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);
    }
  }
}

// // 用于将缓存后的数据帧投影出去的任务
// void drawTaskLoop(void *pvParameters)
// {
//   for (;;)
//   {
//     if (millis() - timeDog3 > 1000)
//     {
//       timeDog3 = millis();
//       TIMERG0.wdt_wprotect = TIMG_WDT_WKEY_VALUE;
//       TIMERG0.wdt_feed = 1;
//       TIMERG0.wdt_wprotect = 0;
//     }
//     if (micros() - timeOld >= kppsTime)
//     {
//       timeOld = micros();
//       draw_task();
//     }
//   }
// }