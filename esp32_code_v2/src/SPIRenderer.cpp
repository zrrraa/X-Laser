#include "SPIRenderer.h"

const int bufferFrames = 3;
static const char *TAGRENDERER = "SPI";

SPIRenderer *renderer;
DynamicJsonDocument doc(4096);
JsonArray avaliableMedia = doc.to<JsonArray>();
int curMedia = -1;

TaskHandle_t fileBufferHandle;

void setupRenderer()
{
  // 打印分配地址之前的RAM
  Serial.print("RAM Before:");
  Serial.println(ESP.getFreeHeap());

  // 分配bufferFrames帧，每一帧MAXRECORDS的内存
  ilda->frames = (ILDA_Frame_t *)malloc(sizeof(ILDA_Frame_t) * bufferFrames);
  if (ilda->frames == NULL)
  {
    Serial.println("ilda->frames ERROR: Failed to allocate");
    while (1)
      ;
  }
  for (int i = 0; i < bufferFrames; i++)
  {
    ilda->frames[i].records = (ILDA_Record_t *)malloc(sizeof(ILDA_Record_t) * MAXRECORDS);
    if (ilda->frames[i].records == NULL)
    {
      Serial.printf("ilda->frames[%d].records ERROR: Failed to allocate\r\n", i);
      while (1)
        ;
    }
  }

  // 打印分配内存后的RAM
  Serial.print("RAM After:");
  Serial.println(ESP.getFreeHeap());

  // 开始准备播放
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

// 开始投影，用IRAM_ATTR将此函数放在RAM中，运行频率更高
void IRAM_ATTR SPIRenderer::draw()
{
  // 这个buffer内已经缓存过内容了，可以投影。————11.20新增的判断条件
  if (ilda->frames[frame_position].isBuffered = true)
  {
    // 这一帧还没画完
    if (draw_position < ilda->frames[frame_position].number_records)
    {
      // 位置信号X&Y的处理和DAC输出
      const ILDA_Record_t &instruction = ilda->frames[frame_position].records[draw_position];
      int y = 2048 + (instruction.x * 1024) / 32768; // 位置信号以两个字节在ILDA文件中储存
      int x = 2048 + (instruction.y * 1024) / 32768; // -32767~+32767-->1024~3072，将位置信号转化为12位数据

      // DAC channel A
      spi_transaction_t t1 = {};
      t1.length = 16;
      t1.flags = SPI_TRANS_USE_TXDATA;
      t1.tx_data[0] = 0b11010000 | ((x >> 8) & 0xF);
      t1.tx_data[1] = x & 255;
      // 发送数据为1101 XXXX XXXX XXXX
      spi_device_polling_transmit(spi, &t1);

      // DAC channel B
      spi_transaction_t t2 = {};
      t2.length = 16;
      t2.flags = SPI_TRANS_USE_TXDATA;
      t2.tx_data[0] = 0b01010000 | ((y >> 8) & 0xF);
      t2.tx_data[1] = y & 255;
      // 发送数据为0101 XXXX XXXX XXXX
      spi_device_polling_transmit(spi, &t2);

      // 判断激光状态标志位和颜色
      if ((instruction.status_code & 0b01000000) == 0) // 一直是这里instruction出错，难道没有分配成功内存？
      // 第二位等于0，开始draw
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

      // 画这一帧中的下一个点
      draw_position++;
    }
    else
    // 这一帧画完了
    {
      // ESP_LOGI(TAGRENDERER, "SPIRenderer running on core %d", xPortGetCoreID());

      ilda->frames[frame_position].isBuffered = false; // 清除这一帧的buffer标志位，表示这一帧缓存的内容已经投影出去了，可以缓存新的内容了
      draw_position = 0;
      frame_position++; // 下一帧

      // 总共只分配了bufferFrames帧的内存空间，循环存放数据帧内容
      if (frame_position >= bufferFrames)
      {
        frame_position = 0;
      }

      // 现阶段无用，isStreaming恒为false
      if (!isStreaming)
      {
        xTaskNotifyGive(fileBufferHandle); // 唤醒filebufferloop，已经消耗了一个buffer，可以进行一次缓存了
      }
    }
  }
}

// 初始化激光控制引脚和DAC的SPI
void SPIRenderer::start()
{
  // 初始化RGB激光的三色控制引脚，定义DAC的刷新引脚
  pinMode(PIN_NUM_LASER_R, OUTPUT);
  pinMode(PIN_NUM_LASER_G, OUTPUT);
  pinMode(PIN_NUM_LASER_B, OUTPUT);
  pinMode(PIN_NUM_LDAC, OUTPUT);

  // SPI初始化
  esp_err_t ret;
  spi_bus_config_t buscfg = {
      .mosi_io_num = PIN_NUM_MOSI,
      .miso_io_num = PIN_NUM_MISO,
      .sclk_io_num = PIN_NUM_CLK,
      .quadwp_io_num = -1,
      .quadhd_io_num = -1,
      .max_transfer_sz = 0,
  };
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
  ret = spi_bus_initialize(HSPI_HOST, &buscfg, 1);
  ESP_LOGI(TAGRENDERER, "HSPI_HOST init, Ret code is %d\n", ret);
  ret = spi_bus_add_device(HSPI_HOST, &devcfg, &spi);
  ESP_LOGI(TAGRENDERER, "HSPI_HOST add device, Ret code is %d\n", ret);

  // 实现任务的函数名称（task1）；任务的任何名称（“ task1”等）；分配给任务的堆栈大小，以字为单位；任务输入参数（可以为NULL）；任务的优先级（0是最低优先级）；任务句柄（可以为NULL）；任务将运行的内核ID（0或1）
  xTaskCreatePinnedToCore(
      fileBufferLoop,
      "fileBufferHandle",
      4096,
      NULL,
      3,
      &fileBufferHandle,
      0);

  // ESP_LOGI(TAGRENDERER, "FileBufferLoop task create on Core 0");
}

// 读取SD卡中的某个ILDA文件
void nextMedia(int position)
{

  curMedia = curMedia + position;

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

  // ESP_LOGI(TAGRENDERER, "animation start!");
}