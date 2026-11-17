//file: HopscotchView.pde
class HopscotchView {

  float corner = 16;
  float shadowOffset = 6;
  float shadowAlpha = 25;

  boolean SHOW_NUMBERS = true; // set true for debugging

  // A simple playful palette
  color[] palette = {
    color(255, 183, 3), // warm yellow
    color(142, 202, 230), // light blue
    color(255, 120, 150), // pink
    color(120, 220, 170), // mint
    color(180, 140, 255)  // lavender
  };

  void display(boolean clearBG) {
    //if (clearBG) background(255);

    for (int row = 0; row < 5; row++) {
      if (row % 2 == 0) {
        drawHopTile(row, 2); // single tile at (row,2)
      } else {
        for (int col = 1; col <= 3; col++) {
          drawHopTile(row, col);  // three tiles at (row,1..3)
        }
      }
    }
  }

  void display() {
    display(true);
  }

  void drawHopTile(int row, int col) {
    GridCell c = grid.cells[row][col];

    // Pick a base color per-tile
    //color base = palette[(int)random(palette.length)];

    // tint
    //base = lerpColor(base, color(255), random(0.05, 0.20));

    // keep glitch tiles slightly "washed"?
    //if (c.isGlitching) {
    //  base = lerpColor(base, color(255), 0.35);
    //}

    //// Subtle shadow
    //noStroke();
    //fill(0, shadowAlpha);
    //rect(c.x + shadowOffset, c.y + shadowOffset, c.size, c.size, corner);

    //// Tile fill (no outline)
    //noStroke();
    //fill(base);
    drawChalk(c);

    if (c.isUserHere) {
      noStroke();
      fill(255, 255, 255, 80);
      rect(c.x, c.y, c.size, c.size, corner);
    }

    // Optional numbers for debugging
    if (SHOW_NUMBERS) {
      fill(0, 30);
      textAlign(CENTER, CENTER);
      //float r = random(20, 32);
      //textSize(r);
      textFont(urbanist);
      textFont(helveticaNeueThin);
      text(c.number, c.x + c.size / 2.0, c.y + c.size / 2.0);
    }
  }

  // Convert continuous colPos to a 5x5 grid col for hopscotch
  int mapHopscotchCol(int row, float colPos) {
    boolean singleRow = (row % 2 == 0);
    if (singleRow) {
      if (colPos >= 2.0 && colPos < 3.0) return 2;
      return -1;
    } else {
      if (colPos >= 1.0 && colPos < 2.0) return 1;
      if (colPos >= 2.0 && colPos < 3.0) return 2;
      if (colPos >= 3.0 && colPos < 4.0) return 3;
      return -1;
    }
  }

  void drawChalk(GridCell c) {
    fill(255);
    strokeWeight(3);
    stroke(0);
    beginShape();
    float x = c.x;
    float y = c.y;
    float w = c.size;
    float h = c.size;

    //Adding random vertex noise for chalk look
    for (int i = 0; i <= 10; i++) {
      vertex(x + w * i/10 + random(-2, 2), y + random(-2, 2));
    }
    for (int i = 0; i <= 10; i++) {
      vertex(x + w + random(-2, 2), y + h * i/10 + random(-2, 2));
    }
    for (int i = 0; i <= 10; i++) {
      vertex(x + w - w * i/10 + random(-2, 2), y + h + random(-2, 2));
    }
    for (int i = 0; i <= 10; i++) {
      vertex(x + random(-2, 2), y + h - h * i/10 + random(-2, 2));
    }
    endShape(CLOSE);
  }
}
