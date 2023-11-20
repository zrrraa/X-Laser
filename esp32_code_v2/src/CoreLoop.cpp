#include "CoreLoop.h"

unsigned long timeDog = 0;
static const char *TAGCORE = "CORELOOP";

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
      // ESP_LOGI(TAGCORE, "fileBufferLoop running on core %d", xPortGetCoreID());

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
      if (!(ilda->tickNextFrame())) // 缓存下一帧。如果缓存不成功，说明三帧都已经缓存了，则将fileBufferLoop置于阻塞状态
      {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
      }
    }
  }
}