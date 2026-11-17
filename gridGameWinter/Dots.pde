class Round2Dots {
  //most of these numbers are pretty arbitrary, i just messed around with them until i thought they looked good
  //if something looks bad or messed up, changing these numbers will probably fix it lol
  float noiseScale = 0.008;
  float timeScale = 0.008;
  float dotSpacing = 17;   //it says dot for a lot of these variables but I changed it to a rectangle
  float maxDotRadius = 9.25;
  float minDotRadius = 0.1;

  // LEVEL 1  palette
  color[] paletteLevel1 = {
    color(208, 208, 208),
    color(186, 186, 186),
    color(174, 174, 174),
    color(159, 159, 159)
  };

  // LEVEL 2 palette
  color[] paletteLevel2 = {
    color(236, 173, 204),
    color(188, 218, 163),
    color(236, 208, 153),
    color(150, 171, 213)
  };

  //uhhhh extra stuff
  color[] accentPalette2 = {
    color(241, 89, 165),
    color(126, 197, 65),
    color(241, 175, 41),
    color(34, 85, 185),
  };


  // Accent color palette stuff
  color[] accentPalette = {
    color(241, 89, 165),
    color(126, 197, 65),
    color(241, 175, 41),
    color(34, 85, 185),
    color(48, 242, 242),
    color(251, 139, 36),
    color(217, 3, 104),
    color(155, 83, 229),
  };

  color[] paletteLevel3 = {
    color(255, 183, 3), // warm yellow
    color(142, 202, 230), // light blue
    color(255, 120, 150), // pink
    color(120, 220, 170), // mint
    color(180, 140, 255)  // lavender
  };

  color[] palette;

  // accent square stuff
  ArrayList<PVector> accentPositions = new ArrayList<PVector>();
  ArrayList<Integer> accentColors = new ArrayList<Integer>();
  int lastAccentUpdate = 0;
  int accentInterval = 2000; // 2 seconds-ish, this is how often the accent dots move
  int accentCount = 25;

  void display() {

    if (currentRound == 1) palette = paletteLevel1;
    else if (currentRound == 2) palette = paletteLevel2;
    else palette = paletteLevel3;

    float t = frameCount * timeScale;
    // looks for all the biggest squares
    if (millis() - lastAccentUpdate > accentInterval) {
      refreshAccents(t);
      lastAccentUpdate = millis();
    }

    noStroke();
    if (currentRound == 3) {
      dotSpacing = 7;
    }
    for (float x = 0; x < width; x += dotSpacing) {
      for (float y = 0; y < height; y += dotSpacing) {
        //uses Prcoessing's perlin noise function
        float n;
        if (currentRound == 1 || currentRound == 2) {
          n = noise(x * noiseScale, y * noiseScale, t);
          //boosts contrast
          n = sharpify(n, 2.2);
        } else {
          n = noise(x * noiseScale * 2, y * noiseScale * 2, t);
          //boosts contrast
          n = sharpify(n, 5.2);
        }
        float r = map(n, 0, 1, minDotRadius, maxDotRadius);
        //skips over the really small stuff
        if (r < 1.2) continue;
        //all color location stuff
        float gx = x / width;
        float gy = y / height;
        //this stuff blends the colors together, it places a color in each corner
        color top    = lerpColor(palette[0], palette[2], gx);
        color bottom = lerpColor(palette[1], palette[3], gx);
        color c      = lerpColor(top, bottom, gy);

        for (int i = 0; i < accentPositions.size(); i++) {
          PVector p = accentPositions.get(i);
          if (p.x == x && p.y == y) {
            c = accentColors.get(i);
            break;
          }
        }

        fill(c);

        // old circle stuff
        //if (currentRound == 3) {
        //  ellipse(x, y, r * 2, r * 2);
        //}
        // theyre rectangles now, i felt like it gave everything a bit more continuity
        //if (currentRound == 1 || currentRound == 2) {
        rect(x - r, y - r, r * 2, r * 2);
        //}
      }
    }
  }
  //this changes which squares are the accent squares
  void refreshAccents(float t) {
    //gets rid of old stuff
    accentPositions.clear();
    accentColors.clear();
    //stores all the possible squares
    ArrayList<PVector> candidates = new ArrayList<PVector>();

    for (float x = 0; x < width; x += dotSpacing) {
      for (float y = 0; y < height; y += dotSpacing) {
        //takes Processing's perlin noise function and converts it to a float
        float n = noise(x * noiseScale, y * noiseScale, t);
        n = sharpify(n, 2.2);

        float r = map(n, 0, 1, minDotRadius, maxDotRadius);
        //chooses teh biggest ones
        if (r > maxDotRadius * 0.85) {
          candidates.add(new PVector(x, y));
        }
      }
    }

    int picks = min(accentCount, candidates.size());
    for (int i = 0; i < picks; i++) {
      int idx = int(random(candidates.size()));
      PVector chosen = candidates.remove(idx);
      accentPositions.add(chosen);

      color ac = accentPalette[int(random(accentPalette.length))];
      accentColors.add(ac);
    }
  }



  //boosts the contrast
  float sharpify(float n, float strength) {
    float centered = n * 2 - 1;
    float sign = centered >= 0 ? 1 : -1;
    float sharpened = sign * pow(abs(centered), 1.0 / strength);
    return (sharpened + 1) / 2.0;
  }
}
