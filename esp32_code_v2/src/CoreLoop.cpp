#include "CoreLoop.h"

unsigned long timeDog = 0;
static const char *TAGCORE = "CORELOOP";
// int kppsTime = 1000000 / (20 * 1000);
// volatile unsigned long timeOld;
// volatile unsigned long timeStart;

void fileBufferLoop(void *pvParameters)
{
  
  for (;;)
  {
    // Serial.print("fileBufferLoop running on core ");
    // Serial.println(xPortGetCoreID());
    if (millis() - timeDog > 1000)
    {
      timeDog = millis();
      TIMERG0.wdt_wprotect = TIMG_WDT_WKEY_VALUE;
      TIMERG0.wdt_feed = 1;
      TIMERG0.wdt_wprotect = 0;
    }
    if (!isStreaming)
    {
      //ESP_LOGI(TAGCORE, "fileBufferLoop!");
      ESP_LOGI(TAGCORE, "fileBufferLoop running on core %d", xPortGetCoreID());
      if (buttonState == 1)
      {
        nextMedia(-1);
        buttonState = 0;
      }
      else if (buttonState == 2)
      {
        nextMedia(1);
        buttonState = 0;
      }
      if (!(ilda->tickNextFrame()))
      {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        // Serial.println("NotifyTake success!");
      }
    }
  }
}

// void Draw_Task(void *pvParameters)
// {
//   for (;;)
//   {
//     if (micros() - timeOld >= kppsTime)
//     {
//       timeOld = micros();
//       draw_task();
//     }
//     button_loop();
//     //Serial.print("mainLoop running on core ");
//     //Serial.println(xPortGetCoreID());
//   }
// }