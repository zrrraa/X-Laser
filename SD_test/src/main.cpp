#include <Arduino.h>
#include <stdio.h>
#include <string.h>
#include <sys/unistd.h>
#include <sys/stat.h>
#include "esp_err.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "sdmmc_cmd.h"
#include "sdkconfig.h"
#include <dirent.h>

#include "ArduinoJson.h"

static const char *TAG = "example";

DynamicJsonDocument doc(4096);
JsonArray avaliableMedia = doc.to<JsonArray>();

#define MOUNT_POINT "/sd"

// This example can use SDMMC and SPI peripherals to communicate with SD card.
// By default, SDMMC peripheral is used.
// To enable SPI mode, uncomment the following line:

// DMA channel to be used by the SPI peripheral
#define SPI_DMA_CHAN 2

// When testing SD and SPI modes, keep in mind that once the card has been
// initialized in SPI mode, it can not be reinitialized in SD mode without
// toggling power to the card.

// Pin mapping when using SPI mode.
// With this mapping, SD card can be used both in SPI and 1-line SD mode.
// Note that a pull-up on CS line is required in SD mode.
#define PIN_NUM_MISO 14
#define PIN_NUM_MOSI 25
#define PIN_NUM_CLK 26
#define PIN_NUM_CS GPIO_NUM_5

void setup()
{
  Serial.begin(115200);
  esp_err_t ret;
  // Options for mounting the filesystem.
  // If format_if_mount_failed is set to true, SD card will be partitioned and
  // formatted in case when mounting fails.
  esp_vfs_fat_sdmmc_mount_config_t mount_config = {                                // 文件系统挂载配置
                                                   .format_if_mount_failed = true, // 如果挂载失败：true会重新分区和格式化/false不会重新分区和格式化
                                                   .max_files = 5,                 // 打开文件最大数量
                                                   .allocation_unit_size = 16 * 1024};
  sdmmc_card_t *card;                     // SD / MMC卡信息结构
  const char mount_point[] = MOUNT_POINT; // 根目录
  ESP_LOGI(TAG, "Initializing SD card");

  // Use settings defined above to initialize SD card and mount FAT filesystem.
  // Note: esp_vfs_fat_sdmmc/sdspi_mount is all-in-one convenience functions.
  // Please check its source code and implement error recovery when developing
  // production applications.
  ESP_LOGI(TAG, "Using SPI peripheral");

  sdmmc_host_t host = SDSPI_HOST_DEFAULT();
  spi_bus_config_t bus_cfg = {
      .mosi_io_num = PIN_NUM_MOSI,
      .miso_io_num = PIN_NUM_MISO,
      .sclk_io_num = PIN_NUM_CLK,
      .quadwp_io_num = -1,
      .quadhd_io_num = -1,
      .max_transfer_sz = 0,
  };
  // SPI总线初始化
  // ret = spi_bus_initialize(host.slot, &bus_cfg, SPI_DMA_CHAN);
  ret = spi_bus_initialize(HSPI_HOST, &bus_cfg, SPI_DMA_CHAN);
  if (ret != ESP_OK)
  {
    ESP_LOGE(TAG, "Failed to initialize bus.");
    return;
  }

  // 这将初始化没有卡检测（CD）和写保护（WP）信号的插槽。
  // 如果您的主板有这些信号，请修改slot_config.gpio_cd和slot_config.gpio_wp。
  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
  slot_config.gpio_cs = PIN_NUM_CS;
  slot_config.host_id = HSPI_HOST;

  // 挂载文件系统
  ret = esp_vfs_fat_sdspi_mount(mount_point, &host, &slot_config, &mount_config, &card);

  if (ret != ESP_OK)
  {
    if (ret == ESP_FAIL)
    {
      ESP_LOGE(TAG, "Failed to mount filesystem. "
                    "If you want the card to be formatted, set the EXAMPLE_FORMAT_IF_MOUNT_FAILED menuconfig option.");
    }
    else
    {
      ESP_LOGE(TAG, "Failed to initialize the card (%s). "
                    "Make sure SD card lines have pull-up resistors in place.",
               esp_err_to_name(ret));
    }
    return;
  }

  // Card has been initialized, print its properties
  sdmmc_card_print_info(stdout, card);

  DIR *dir = opendir("/sd/ILDA");
  Serial.println("Open success");
  if (dir == NULL)
  {
    Serial.println("Failed to open directory");
    return;
  }
  Serial.println("Open success");
  struct dirent *entry;
  while ((entry = readdir(dir)) != NULL)
  {
    if (entry->d_type == DT_REG && strstr(entry->d_name, ".ild") != NULL)
    {
      //Serial.println(entry->d_name);
      ESP_LOGI(TAG, "%s", entry->d_name);
      avaliableMedia.add(String(entry->d_name)); // 只读个名字，内容边render边read
      // 将文件名添加到 avaliableMedia 列表中
    }
  }

  closedir(dir);

  // 卸载分区并禁用SDMMC或SPI外设
  esp_vfs_fat_sdcard_unmount(mount_point, card);
  ESP_LOGI(TAG, "Card unmounted");

  // 卸载总线
  spi_bus_free(HSPI_HOST);
}

void loop()
{
}
