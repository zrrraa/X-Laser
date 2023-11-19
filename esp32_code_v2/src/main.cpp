#include "main.h"

// int kppsTime = 1000000 / (20 * 1000);
int kppsTime = 50;
volatile unsigned long timeOld;
volatile unsigned long timeStart;

// TaskHandle_t TFTLCD;
static const char *TAGMAIN = "MAIN";

void MyUI(void *pvParameters);

void setup()
{
  Serial.begin(115200);

  // CS PULL UP
  digitalWrite(15, HIGH);
  digitalWrite(21, HIGH);
  digitalWrite(5, HIGH);
  digitalWrite(27, HIGH);

  setupSD();

  web_init();
  // lcd_init();

  // xTaskCreatePinnedToCore(
  //     MyUI,     /* Task function. */
  //     "TFTLCD", /* name of task. */
  //     4096,    /* Stack size of task */
  //     NULL,     /* parameter of the task */
  //     3,        /* priority of the task */
  //     NULL,     /* Task handle to keep track of created task */
  //     0);       /* pin task to core 0 */
  // delay(500);
  setupRenderer();
  button_init();
  // xTaskCreatePinnedToCore(Draw_Task, "drawing", 8192, NULL, 1, &drawing, 1);
  // Serial.println("Draw_Task create on Core 1");
  // delay(1000);
}

void loop()
{
  // ESP_LOGI(TAGMAIN, "MAINLOOP running!");
  if (micros() - timeOld >= kppsTime)
  {
    // ESP_LOGI(TAGMAIN, "DRAW running!");
    timeOld = micros();
    draw_task();
  }
  // lcd_loop();
  button_loop();
  // Serial.print("main_loop running on core ");
  // Serial.println(xPortGetCoreID());
}

void MyUI(void *pvParameters)
{
  // Serial.print("Task1 running on core ");
  // Serial.println(xPortGetCoreID());
  lcd_init();
  for (;;)
  {
    // digitalWrite(led1, HIGH);
    // delay(1000);
    // digitalWrite(led1, LOW);
    // delay(1000);

    // ESP_LOGI(TAGMAIN, "TFTLCD running on core %d", xPortGetCoreID());
    lcd_loop();
  }
}