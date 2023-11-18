#include "SPIRenderer.h"

const int bufferFrames = 3;
static const char *TAGRENDERER = "SPI";
// Ticker drawer;
SPIRenderer *renderer;
DynamicJsonDocument doc(4096);
JsonArray avaliableMedia = doc.to<JsonArray>();
int curMedia = -1;

TaskHandle_t fileBufferHandle;

int debug_flag = 0;

void setupRenderer()
{
  Serial.print("RAM Before:");
  Serial.println(ESP.getFreeHeap());
  ilda->frames = (ILDA_Frame_t *)malloc(sizeof(ILDA_Frame_t) * bufferFrames);
  for (int i = 0; i < bufferFrames; i++)
  {
    ilda->frames[i].records = (ILDA_Record_t *)malloc(sizeof(ILDA_Record_t) * MAXRECORDS);
  }
  Serial.print("RAM After:");
  Serial.println(ESP.getFreeHeap());
  nextMedia(1);
  renderer = new SPIRenderer();
  renderer->start();
}

void draw_task()
{
  renderer->draw();
}

SPIRenderer::SPIRenderer()
{
  frame_position = 0; // 第几帧
  draw_position = 0;  // 一帧中的第几个点
}

void IRAM_ATTR SPIRenderer::draw()
{
  // Clear the interrupt
  // do we still have things to draw?
  // Serial.println(ilda->frames[frame_position].number_records);
  // Serial.println(frame_position);

  if (draw_position < ilda->frames[frame_position].number_records) // 这一帧还没画完
  {
    const ILDA_Record_t &instruction = ilda->frames[frame_position].records[draw_position];
    int y = 2048 + (instruction.x * 1024) / 32768; // 位置信号以两个字节在ILDA文件中储存
    int x = 2048 + (instruction.y * 1024) / 32768; // -32767~+32767-->1024~3072，将位置信号转化为12位数据
    // Serial.print(instruction.x);
    // Serial.print(" ");
    // Serial.println(instruction.y);
    //  set the laser state

    // channel A
    spi_transaction_t t1 = {};
    t1.length = 16;
    t1.flags = SPI_TRANS_USE_TXDATA;
    t1.tx_data[0] = 0b11010000 | ((x >> 8) & 0xF);
    t1.tx_data[1] = x & 255;
    // 发送数据为1101 XXXX XXXX XXXX
    spi_device_polling_transmit(spi, &t1);

    // channel B
    spi_transaction_t t2 = {};
    t2.length = 16;
    t2.flags = SPI_TRANS_USE_TXDATA;
    t2.tx_data[0] = 0b01010000 | ((y >> 8) & 0xF);
    t2.tx_data[1] = y & 255;
    // 发送数据为0101 XXXX XXXX XXXX
    spi_device_polling_transmit(spi, &t2);

    // Serial.println(instruction.status_code);
    //  判断激光状态标志位和颜色
    if ((instruction.status_code & 0b01000000) == 0) // 一直是这里instruction出错，难道没有分配成功内存？
    // 这里根据文件定义，应该是不等于0时会亮才对，暂时不懂
    {
      if (instruction.color <= 9)
      { // RED
        digitalWrite(PIN_NUM_LASER_R, LOW);
      }
      else if (instruction.color <= 18)
      { // YELLOW
        digitalWrite(PIN_NUM_LASER_R, LOW);
        digitalWrite(PIN_NUM_LASER_G, LOW);
      }
      else if (instruction.color <= 27)
      { // GREEN
        digitalWrite(PIN_NUM_LASER_G, LOW);
      }
      else if (instruction.color <= 36)
      { // CYAN
        digitalWrite(PIN_NUM_LASER_G, LOW);
        digitalWrite(PIN_NUM_LASER_B, LOW);
      }
      else if (instruction.color <= 45)
      { // BLUE
        digitalWrite(PIN_NUM_LASER_B, LOW);
      }
      else if (instruction.color <= 54)
      { // Magenta
        digitalWrite(PIN_NUM_LASER_B, LOW);
        digitalWrite(PIN_NUM_LASER_R, LOW);
      }
      else if (instruction.color <= 63)
      { // WHITE
        digitalWrite(PIN_NUM_LASER_B, LOW);
        digitalWrite(PIN_NUM_LASER_R, LOW);
        digitalWrite(PIN_NUM_LASER_G, LOW);
      }
    }
    else
    { // 不亮的Point
      digitalWrite(PIN_NUM_LASER_R, HIGH);
      digitalWrite(PIN_NUM_LASER_G, HIGH);
      digitalWrite(PIN_NUM_LASER_B, HIGH);
    }
    // DAC Load
    digitalWrite(PIN_NUM_LDAC, LOW);
    digitalWrite(PIN_NUM_LDAC, HIGH);

    draw_position++;
  }
  else
  {
    ESP_LOGI(TAGRENDERER, "SPIRenderer running on core %d", xPortGetCoreID());
    ilda->frames[frame_position].isBuffered = false;
    draw_position = 0;
    frame_position++;
    // Serial.println("frame++");
    // debug_flag++;
    if (frame_position >= bufferFrames)
    {
      
      frame_position = 0;
    }
    if (!isStreaming) // 现阶段无用
    {
      // Serial.println("next fileBufferHandle");
      xTaskNotifyGive(fileBufferHandle);
      // Serial.println("NotifyGiven success!");
    }
  }
}

void SPIRenderer::start()
{
  pinMode(PIN_NUM_LASER_R, OUTPUT);
  pinMode(PIN_NUM_LASER_G, OUTPUT);
  pinMode(PIN_NUM_LASER_B, OUTPUT);
  pinMode(PIN_NUM_LDAC, OUTPUT);

  // setup SPI output
  esp_err_t ret;
  spi_bus_config_t buscfg = {
      .mosi_io_num = PIN_NUM_MOSI,
      .miso_io_num = PIN_NUM_MISO,
      .sclk_io_num = PIN_NUM_CLK,
      .quadwp_io_num = -1,
      .quadhd_io_num = -1,
      .max_transfer_sz = 0};
  spi_device_interface_config_t devcfg = {
      .command_bits = 0,
      .address_bits = 0,
      .dummy_bits = 0,
      .mode = 0,
      .clock_speed_hz = 40000000,
      .spics_io_num = PIN_NUM_CS, // CS pin
      .flags = SPI_DEVICE_NO_DUMMY,
      .queue_size = 2,
  };
  // Initialize the SPI bus
  ret = spi_bus_initialize(HSPI_HOST, &buscfg, 1);
  printf("Ret code is %d\n", ret);
  ret = spi_bus_add_device(HSPI_HOST, &devcfg, &spi);
  printf("Ret code is %d\n", ret);

  // 实现任务的函数名称（task1）；任务的任何名称（“ task1”等）；分配给任务的堆栈大小，以字为单位；任务输入参数（可以为NULL）；任务的优先级（0是最低优先级）；任务句柄（可以为NULL）；任务将运行的内核ID（0或1）
  xTaskCreatePinnedToCore(
      fileBufferLoop, "fileBufferHandle", 4096 // Stack size
      ,
      NULL, 3 // Priority
      ,
      &fileBufferHandle, 0); // 0 pro_cpu  1 app_cpu
  // delay(5000);
  // vTaskDelay(4000 / portTICK_PERIOD_MS); // 4s
  ESP_LOGI(TAGRENDERER, "FileBufferLoop task create on Core 0");
}

void nextMedia(int position)
{
  // delete ilda;
  // ilda = new ILDAFile();

  // curMedia = curMedia + position;
  // Serial.println(position);
  // Serial.println(curMedia);
  // Serial.println(avaliableMedia.size());
  curMedia = curMedia + position;
  // Serial.println(curMedia);
  if (curMedia < 0)
  {
    curMedia = avaliableMedia.size() - 1;
  }
  if (curMedia >= avaliableMedia.size()) // 先做大于等于的判断会出错，size是无符号数，-1>=size成立
  {
    curMedia = 0;
  }
  String filePath = String("/ILDA/") += avaliableMedia[curMedia].as<String>();
  ilda->cur_frame = 0;
  ilda->read(SD, filePath.c_str());
  ESP_LOGI(TAGRENDERER, "animation start!");
}