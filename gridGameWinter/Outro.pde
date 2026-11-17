class OutroScreen {
  int stage = 0;
  int startTime = 0;

  void nextStage() {
    if (stage < 3) {
      stage++;
      startTime = millis();
    }
  }

  void display() {
    if (stage == 0) return;

    int time = millis() - startTime;
    pushStyle();
    noStroke();

    if (stage == 1) {
      if (time < 300 || (time < 800 && frameCount % 4 < 2)) {
        fill(0, 0, 255);
        rect(0, height/2, width, height/2);
      }
    }

    if (stage == 2 && time < 500) {
      fill(0);
      rect(0, 0, width, height);
      fill(0, 0, 255);
      rect(0, 0, width, height/2);
      fill(0, 255, 80);
      rect(0, height/2, width, 8);
      rect(0,(height/2)+5, width, 12);

      fill(255);
     // textFont(urbanist);
     textFont(helveticaNeueMedium);
      textSize(26);
      textAlign(CENTER, CENTER);
      text("HDMI", width/2, height/4 - 30);
      text("No Signal", width/2, height/4 + 10);
    }

    if (stage == 3) {
      if (time < 500) background(0, 0, 255);
      else background(0);
    }

    popStyle();
  }
}
