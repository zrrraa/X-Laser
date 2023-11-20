#include "SDCard.h"

File root;

void setupSD()
{
  if (!SD.begin())
  {
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD.cardType();

  if (cardType == CARD_NONE)
  {
    Serial.println("No SD card attached");
    return;
  }

  Serial.print("SD Card Type: ");
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

  uint64_t cardSize = SD.cardSize() / (1024 * 1024);
  Serial.printf("SD Card Size: %lluMB\r\n", cardSize);

  root = SD.open("/ILDA");
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
}