#include "main.h"

// int kppsTime = 1000000 / (20 * 1000);
int kppsTime = 50;
volatile unsigned long timeOld;
volatile unsigned long timeStart;

// TaskHandle_t drawing;
TaskHandle_t Task1;

void setup()
{
  Serial.begin(115200);
  setupSD();

  web_init();

  // xTaskCreatePinnedToCore(
  //     Task1code, /* Task function. */
  //     "Task1",   /* name of task. */
  //     10000,     /* Stack size of task */
  //     NULL,      /* parameter of the task */
  //     3,         /* priority of the task */
  //     &Task1,    /* Task handle to keep track of created task */
  //     0);        /* pin task to core 0 */
  // delay(500);

  setupRenderer();
  button_init();
  // xTaskCreatePinnedToCore(Draw_Task, "drawing", 8192, NULL, 1, &drawing, 1);
  //  Serial.println("Draw_Task create on Core 1");
  //  delay(1000);
}

void loop()
{
  if (micros() - timeOld >= kppsTime)
  {
    timeOld = micros();
    draw_task();
  }
  button_loop();
  // Serial.print("main_loop running on core ");
  // Serial.println(xPortGetCoreID());
}

void Task1code(void *pvParameters)
{
  Serial.print("Task1 running on core ");
  Serial.println(xPortGetCoreID());

  for (;;)
  {
    // digitalWrite(led1, HIGH);
    // delay(1000);
    // digitalWrite(led1, LOW);
    // delay(1000);

    // ESP_LOGI(TAG, "Task1 running on core %d", xPortGetCoreID());
  }
}