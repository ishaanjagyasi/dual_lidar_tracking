class ScoreTracker {
  // State
  int successPoints = 0;
  float confidencePoints = 0.5;  // direct confidence score from 0.0 to 1.0

  // Left in place, but no longer using these variables for main scoring logic
  float a = 2.0;
  float b = 2.0;
  float r = 0.0;
  float i = 0.7;

  final float w = 1.0;
  final float gainPlay = 0.03;
  final float dropBiasFromPlay = 0.01;
  final float kSurprise = 0.05;
  final float kFail = 0.02;
  final float kPlay = 0.25;
  final float kBias = 0.7;

  boolean silenceGlitchApplied = false;

  void onOffGridEntered() {
    confidencePoints = clamp01(confidencePoints + 0.03);
  }

  void onBellHit() {
    if (currentRound == 1) {
      // Round 1: achievement up, confidence down
      successPoints += 1;
      confidencePoints = clamp01(confidencePoints - 0.12);
    } else if (currentRound == 2) {
      successPoints += 1; //bug fix: confidence now changes randomly on round 2 when user hits glitch tile
      if (random(1) < 0.5) {
        confidencePoints = clamp01(confidencePoints + 0.12);
      } else {
        confidencePoints = clamp01(confidencePoints - 0.12);
      }
    } else {
      // Round 3: both go up together
      successPoints += 1.5;
      confidencePoints = clamp01(confidencePoints + 0.13);
    }
  }

  void onGlitchMiss() {
    successPoints -= 1;
    if (successPoints < 0) successPoints = 0;

  }

  float getConfidence() {
    return clamp01(confidencePoints);
  }

  void applySilenceGlitchSupportive() {
    if (silenceGlitchApplied) return;
    silenceGlitchApplied = true;
    successPoints = 0;
  }


  // UI
  // segmented bar settings
  int NUM_SEGS = 10; // segments per bar
  int SEG_STEP = 40; // distance between segment starts
  int SEG_W = SEG_STEP;// neighbors share a border
  int SEG_H = 40;// same height as your original bars

  void display() {
    float confidence = getConfidence();

    fill(0);
    textAlign(LEFT, CENTER);
    textFont(helveticaNeueBold);

    textSize(50);
    text("ACHIEVEMENT", 40, 45);
    drawSegBar(40, 75, successPoints, 10, color(26, 197, 65));
    fill(0);

    // Confidence moves to top-right
    textAlign(LEFT, CENTER);
    text("CONFIDENCE", width - 380, 45);
    drawSegBar(width - 450, 75, confidence, 1.0, color(34, 85, 185));
    fill(0);
  }


  void drawSegBar(float x, float y, float value, float maxVal, color base) {
    pushStyle();
    noStroke();

    float v = constrain(value, 0, maxVal);
    int filled = floor(v / maxVal * NUM_SEGS + 0.0001);//small epsilon avoids float rounding misses

    for (int s = 0; s < NUM_SEGS; s++) {
      drawSegment(x + s * SEG_STEP, y, s < filled, base);
    }
    popStyle();
  }

  void drawSegment(float x, float y, boolean isFilled, color base) {

    noStroke();

    float ix = x, iy = y;
    float iw = SEG_W, ih = SEG_H ;

    if (isFilled) {
      fill(base);
      rect(ix, iy, iw, ih);
    }

    noFill();
    int strokeThick = 2;
    stroke(0);
    strokeWeight(strokeThick);
    rect(x, y, SEG_W, SEG_H);

    noStroke();
  }

  float clamp01(float v) {
    return constrain(v, 0, 1);
  }

  void resetAllScores() {
    successPoints = 0;
    confidencePoints = 0.5;
    a = 2.0;
    b = 2.0;
    r = 0.0;
    i = 0.7;
    silenceGlitchApplied = false;
  }
}
