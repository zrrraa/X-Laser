#include "SDCard.h"

File root;

void setupSD()
{
  Serial.println("Initializing SD card...");
  if (!SD_MMC.begin("/sdcard", true))
  {
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD_MMC.cardType();

  if (cardType == CARD_NONE)
  {
    Serial.println("No SD_MMC card attached");
    return;
  }

  Serial.print("SD_MMC Card Type: ");
  if (cardType == CARD_MMC)
  {
    Serial.println("MMC");
  }
  else if (cardType == CARD_SD)
  {
    Serial.println("SDSC");
  }
  else if (cardType == CARD_SDHC)
  {
    Serial.println("SDHC");
  }
  else
  {
    Serial.println("UNKNOWN");
  }

  uint64_t cardSize = SD_MMC.cardSize() / (1024 * 1024);
  Serial.printf("SD_MMC Card Size: %lluMB\r\n", cardSize);

  root = SD_MMC.open("/ILDA");
  while (true)
  {
    File entry = root.openNextFile();
    if (!entry)
    {
      break;
    }
    if (!entry.isDirectory() && String(entry.name()).indexOf(".ild") != -1)
    {
      Serial.println(entry.name());
      avaliableMedia.add(String(entry.name()));
    }
  }

  String avaliableOptions = "";
  for (uint16_t i = 0; i < avaliableMedia.size(); i++)
  {
    String mediaString = avaliableMedia[i].as<String>();

    int ildIndex = mediaString.lastIndexOf(".ild"); // 寻找 '.ild' 扩展名的位置
    if (ildIndex != -1)
    {
      mediaString = mediaString.substring(0, ildIndex); // 如果找到 '.ild'，只保留前面的部分
    }

    // 如果ILDA动画名称长度超过15，只取前15个字符
    if (mediaString.length() > 15)
    {
      mediaString = mediaString.substring(0, 15);
    }
    avaliableOptions += mediaString;

    if (i != avaliableMedia.size() - 1)
    {
      avaliableOptions += "\n";
    }
  }

  const char *options = avaliableOptions.c_str();

  lv_roller_set_options(ui_Roller1, options, LV_ROLLER_MODE_INFINITE);
}