#include "CoreLoop.h"

bool isStreaming = false;
unsigned long timeDog = 0;

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
      if (!ilda->tickNextFrame())
      {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        // Serial.println("NotifyTake success!");
      }
    }
  }
}