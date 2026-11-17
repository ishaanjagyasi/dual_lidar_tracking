class LetterGlitch {

  String phrase = "WWHEREDOIGO?";
  ArrayList<PVector> positions = new ArrayList<PVector>();
  ArrayList<Float> sizes = new ArrayList<Float>();
  ArrayList<Float> angles = new ArrayList<Float>();
  ArrayList<Character> chars = new ArrayList<Character>();
  ArrayList<Integer> colors = new ArrayList<Integer>();
  ArrayList<PFont> fonts = new ArrayList<PFont>();

  void addLetter() {

    char c = phrase.charAt(int(random(phrase.length())));
    chars.add(c);

    // size
    if (random(1) < 0.15) sizes.add(random(300, 450));
    else sizes.add(random(40, 100));

    // zone stuff
    int zone = sliceForChar(c);
    float slice = width / 12.0;
    //float preferredX = zone * slice + slice/2;
    float preferredX = zone * slice;
    float x = preferredX + random(-slice*0.1, slice*0.1);
    x = constrain(x, 0, width);


    float y = random(height);
    positions.add(new PVector(x, y));

    // rotation
    angles.add(random(-45, 45));

    // color
    colors.add(round2Dots.accentPalette2[int(random(round2Dots.accentPalette2.length))]);

    // font
    PFont f;
    float r = random(1);
    if (r < 0.25) f = myFont1;
    else if (r < 0.50) f = myFont2;
    else if (r < 0.75) f = myFont13;
    else f = urbanist;

    fonts.add(f);
  }


  void display() {
    for (int i = 0; i < chars.size(); i++) {
      pushMatrix();
      translate(positions.get(i).x, positions.get(i).y);
      rotate(radians(angles.get(i)));

      textFont(fonts.get(i));
      textSize(sizes.get(i));
      fill(colors.get(i));

      text(chars.get(i), 0, 0);
      popMatrix();
    }
  }
  void reset() {
    positions.clear();
    sizes.clear();
    angles.clear();
    chars.clear();
    colors.clear();
    fonts.clear();
  }
}



//other stuff
int sliceForChar(char c) {
  switch(c) {

  case 'W':
    return random(1) < 0.5 ? 0 : 1;
  case 'H':
    return 2;

  case 'E':
    return random(1) < 0.5 ? 3 : 5;  // two E's

  case 'R':
    return 4;

  case 'D':
    return 6;

  case 'O':
    return random(1) < 0.5 ? 7 : 10;  // two O's

  case 'I':
    return 8;

  case 'G':
    return 9;

  case '?':
    return 11;

    //just in case lol
  default:
    return 6;
  }
}
