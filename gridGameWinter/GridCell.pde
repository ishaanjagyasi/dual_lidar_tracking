//file: GridCell.pde
class GridCell {
  float x, y;
  int size;
  int number;
  int row, col;
  boolean isGlitching = false;
  boolean isUserHere = false;


  GridCell(float x, float y, int size, int number, int row, int col) {
    this.x = x;
    this.y = y;
    this.size = size;
    this.number = number;
    this.row = row;
    this.col = col;
  }

  void display() {
    // base tile
    if (currentRound == 1) fill(208);
    else if (currentRound == 2) fill(233);
    else fill(255);
    stroke(0);
    strokeWeight(3);
    rect(x, y, size, size);

    fill(0);
    textAlign(CENTER, CENTER);
    textSize(32);
    textFont(helveticaNeueMedium);
    text(number, x + size / 2.0, y + size / 2.0);

    if (isGlitching) drawGlitchSlices();

    // outline on top so slices dont spill past the border
    noFill();
    stroke(0);
    strokeWeight(3);
    rect(x, y, size, size);

    drawNumber();
  }

  float hash(int a, int b, int c) {
    float v = sin(a * 12.9898 + b * 78.233 + c * 37.719) * 43758.5453;
    //println(v);
    return v - floor(v);   // 0..1, same inputs always give the same output
    
  }

  void drawNumber() {
    textAlign(CENTER, CENTER);
    textSize(32);
    //textFont(urbanist);
    float cx = x + size / 2.0, cy = y + size / 2.0;

    if (isGlitching && glitchOn()) {
      color[] pal = round2Dots.accentPalette;
      int s = glitchStep();
      float split = 2 + hash(s, number, 5) * 5;
      float jitterY = (hash(s, number, 6) - 0.5) * 6;
      noStroke();
      fill(pal[int(hash(s, number, 7) * pal.length) % pal.length]);
      text(number, cx - split, cy + jitterY);
      fill(pal[int(hash(s, number, 8) * pal.length) % pal.length]);
      text(number, cx + split, cy - jitterY);
    }
    fill(0);
    text(number, cx, cy);
  }

  int glitchStep() {
    return millis() / 70;
  }

  boolean glitchOn() {
    int tileSeed = row * 31 + col * 17;
    return hash(glitchStep() / 3, tileSeed, 1) < 0.65;
  }

  void drawGlitchSlices() {
    if (!glitchOn()) return;

    color[] pal = round2Dots.accentPalette;
    int tileSeed = row * 31 + col * 17;
    int s = glitchStep();
    int burst = s / 3;

    color c1 = pal[int(hash(burst, tileSeed, 2) * pal.length) % pal.length];
    color c2 = pal[int(hash(burst, tileSeed, 3) * pal.length) % pal.length];

    int nSlices = 2 + int(hash(s, tileSeed, 4) * 5);

    pushStyle();
    clip(x, y, size, size);
    noStroke();
    for (int i = 0; i < nSlices; i++) {
      float sy = hash(s, tileSeed, 10 + i) * size;
      float sh = 2 + pow(hash(s, tileSeed, 20 + i), 2) * size * 0.35;
      float dx = (hash(s, tileSeed, 30 + i) - 0.5) * size * 0.8;
      fill(hash(s, tileSeed, 40 + i) < 0.7 ? c1 : c2);
      rect(x + dx, y + sy, size, sh);
    }

    if (hash(s, tileSeed, 99) < 0.25) {
      fill(0, 90);
      for (float ly = y; ly < y + size; ly += 4) rect(x, ly, size, 1);
    }
    noClip();
    popStyle();
  }
}
