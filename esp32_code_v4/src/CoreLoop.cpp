#include "CoreLoop.h"

static const char *TAGCORE = "CORELOOP";

unsigned long timeDog = 0;
unsigned long timeDog2 = 0;
unsigned long timeDog3 = 0;


// unsigned long LCD_freshPrevious = 0;
// unsigned long LCD_freshInterval = 1000 / 1000; // 1000Hz刷新LCD屏

// int kppsTime = 1000000 / (20 * 1000); // 20kHz
// volatile unsigned long timeOld;
// volatile unsigned long timeStart;

// 用于不断地将数据帧缓存到申请的三帧中去。一次fileBufferLoop会将一个数据帧的内容缓存到一个buffer中去
// fileBufferLoop执行的很快，不停的缓存，如果缓存满了则置于阻塞状态，投影出去，消耗了数据帧后会把它唤醒
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
    if (!isStreaming)
    {
      // 物理按键状态判断，可能不用了但是写着备用
      // if (buttonState == 1)
      // {
      //   nextMedia(-1);
      //   buttonState = 0;
      // }
      // else if (buttonState == 2)
      // {
      //   nextMedia(1);
      //   buttonState = 0;
      // }

      // TFTLCD按钮判断
      if (TFTLCD_BUTTON == 1)
      {
        nextMedia(0 - curMedia);
        TFTLCD_BUTTON = 0;
        
      }
      else if (TFTLCD_BUTTON == 2)
      {
        nextMedia(1 - curMedia);
        TFTLCD_BUTTON = 0;
        
      }
      else if (TFTLCD_BUTTON == 3)
      {
        nextMedia(2 - curMedia);
        TFTLCD_BUTTON = 0;
        
      }
      else if (TFTLCD_BUTTON == 4)
      {
        nextMedia(3 - curMedia);
        TFTLCD_BUTTON = 0;
        
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