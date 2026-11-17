// TODO: change glitch color switching to pulsating
// TODO: cant start glitching after user steps on tile
//TODO: move 0,0 to right corner
//TODO: make tile 24 glitch pulsating instead of flickering
//TODO: fade background out after level 3 keep grid
//TODO: debugging ball glitch
import oscP5.*;
import netP5.*;

//Font Stuff: check
PFont myFont1;
PFont myFont2;
PFont urbanist;

//landing page stuff
boolean showLanding = true;
PFont[] landingFonts;
int landingFontIndex = 0;
int landingFrameCounter = 0;
float[] landingFontSizes;
int landingAccentColor = 0;

//updates fonts
PFont helveticaNeueMedium;
PFont helveticaNeueBold;
PFont helveticaNeueThin;

//landing page fonts
//in order of squariness to letteriness
PFont myFont6;
PFont myFont7;
PFont myFont8;
PFont myFont9;
PFont myFont10;
PFont myFont11;
PFont myFont12;
PFont myFont13;



//dot stuff:
Round2Dots round2Dots;


OscP5 oscP5;
NetAddress remoteAddress;
NetAddress pythonResetAddress;
OscP5 oscP5Max; // second listener for Max new round messages (port 9400)

int gridRows = 5;
int gridCols = 5;
int cellSize = 110; //we want it to be 14inx14in

//globals so we know exactly where lines are drawn
int gridOffsetX;
int gridOffsetY;

Grid grid;
User user;
OSCSender sendingOSC;
OSCReceiveClass receivingOSC;
ScoreTracker scoreTracker;
HopscotchView hopView;
BallGlitch ballGlitch;
//ConfettiGlitch confettiGlitch;
ReentryGuidance reentryGuidance;

LetterGlitch letterGlitch;

//outro stuff
OutroScreen outroScreen;
boolean showingOutro = false;
int outroDuration = 1000000;
//int outroDuration = 7 * 60 * 1000;

//round variables
int currentRound = 1;
int totalRounds = 3;
int roundDuration = 7 * 60 * 1000;
int roundStartTime;
boolean showingRoundScreen = true;
int roundScreenStartTime;
boolean isRestrictedColumnRound = false;
boolean USE_TIMER = false;
boolean WAIT_FOR_MAX = true;
String roundScreenLabel = "Waiting for Max…";

//debugging sensor variables
float dbgPosXTiles = 0;
float dbgPosYTiles = 0;
int dbgTileX = 0;
int dbgTileY = 0;
ArrayList<PVector> dbgTrail = new ArrayList<PVector>();
int dbgTrailMax = 200;
boolean SHOW_TRAIL = false;

void advanceToNextRound() {
  if (currentRound < totalRounds) {
    currentRound++;
    roundScreenLabel = "Level " + currentRound;
    WAIT_FOR_MAX = false;
    showingRoundScreen = true;
    roundScreenStartTime = millis();

    isRestrictedColumnRound = (currentRound == 3);

    grid = new Grid(gridRows, gridCols, cellSize);
  }

  if (currentRound == 3) {
    isRestrictedColumnRound = false;
    grid = new Grid(gridRows, gridCols, cellSize);
  } else {
    isRestrictedColumnRound = false;
    grid = new Grid(gridRows, gridCols, cellSize);
  }

  user = new User();
  if (reentryGuidance != null) reentryGuidance.reset();
}

void setup() {
  fullScreen();
  //size(900,900);
  windowTitle("Where do I Go?");


  urbanist = createFont("Urbanist-Medium.ttf", 32, true);
  textFont(urbanist);
  //loading new fonts
  helveticaNeueMedium = createFont("HelveticaNeueMedium.otf", 32, true);
  helveticaNeueBold = createFont("HelveticaNeueBold.otf", 32, true);
  helveticaNeueThin = createFont("HelveticaNeueThin.otf", 32, true);


  myFont1 = createFont("NeutralFace.otf", 65, true);
  myFont2 = createFont("Urbanist-Medium.ttf", 40, true);
  //most square
  myFont6 = createFont("HeavySquare-Color.ttf", 32, true);
  myFont7 = createFont("Square Chunks.ttf", 32, true);
  myFont8 = createFont("so_square.ttf", 32, true);
  myFont9 = createFont("pixel_script.ttf", 32, true);
  myFont10 = createFont("8-bit-pusab.ttf", 32, true);
  myFont11 = createFont("LLPIXEL3.ttf", 32, true);
  myFont12 = createFont("Pixel Square 10.ttf", 32, true);
  //least square
  myFont13 = createFont("Cavalhatriz.ttf", 32, true);
  //random one

  landingFonts = new PFont[] {
    myFont6,
    myFont7,
    myFont8,
    myFont9,
    myFont10,
    myFont11,
    myFont12,
    myFont13,
    urbanist
  };

  landingFontSizes = new float[] {
    200, //myfont6
    140,
    140,
    140,
    90,
    160,
    150,
    140, // myont13
    120   // urbanist
  };


  round2Dots = new Round2Dots();

  grid = new Grid(gridRows, gridCols, cellSize);
  user = new User();
  scoreTracker = new ScoreTracker();
  hopView = new HopscotchView();

  //outo stuff
  outroScreen = new OutroScreen();

  oscP5 = new OscP5(this, 6800);
  oscP5Max = new OscP5(this, 9400);
  remoteAddress = new NetAddress("127.0.0.1", 8100);
  pythonResetAddress = new NetAddress("127.0.0.1", 6801);
  println("Listening OSC: sensor=6800, maxCues=9400");
  ballGlitch = new BallGlitch();
  reentryGuidance = new ReentryGuidance();

  sendingOSC = new OSCSender();
  receivingOSC = new OSCReceiveClass();

  roundScreenStartTime = millis();

  WAIT_FOR_MAX = true;
  showingRoundScreen = true;
  roundScreenLabel = "Level " + currentRound;
  println("Waiting for Max… (send /level1begins 1 to start)");
}
/*
void startOutro() {
 if (showingOutro) return;
 
 showingOutro = true;
 outroScreen.reset();
 
 }
 */
void draw() {



  if (showLanding) {
    displayLandingScreen();
    return;
  }

  //level specific bg stuff
  if (currentRound == 1) background(208);
  else if (currentRound == 2) background(233);
  else background(255);

  //i only have the funky background in levels 1 and 2 since it might be distracting in level 3

  //use this condition for white bacground in round 3
  //if ((currentRound == 1 || currentRound == 2) && !showingRoundScreen) {
  if (!showingRoundScreen) {
    round2Dots.display();
  }

  if (showingRoundScreen) {
    fill(0);
    textAlign(CENTER);
    textSize(64);
    // textFont(urbanist);   // new font
    textFont(helveticaNeueMedium);
    text("Level " + currentRound, width/2, height/2);

    if (millis() - roundScreenStartTime > 3000) {
      showingRoundScreen = false;
      WAIT_FOR_MAX = false;
      roundStartTime = millis();
      needsCalibration = true;
    }
  } else {
    if (currentRound == 3) hopView.display();
    else grid.display();

    reentryGuidance.display();
    user.display();

    if (frameCount % 2 == 0) sendingOSC.sendOSC();

    if (USE_TIMER && currentRound < totalRounds && (millis() - roundStartTime > roundDuration)) {
      advanceToNextRound();
    }
  }


  scoreTracker.display();


  if (SHOW_TRAIL) { //debugging trace
    noFill();
    stroke(255, 0, 0, 150);
    strokeWeight(2);
    for (PVector p : dbgTrail) {
      ellipse(p.x, p.y, 6, 6);
    }
  }
  outroScreen.display();
}

void keyPressed() {
  if (key == 'r' || key == 'R') {
    println("New Round");
    needsCalibration = true;
    sendingOSC.sendOSC();
  }

  if (key == 'n' || key == 'N') {
    if (!showingRoundScreen) {
      advanceToNextRound();
    }
  }

  if (key == 'w' || key == 'W') user.updatePosition(user.currentRow - 1, user.currentCol);
  if (key == 's' || key == 'S') user.updatePosition(user.currentRow + 1, user.currentCol);
  if (key == 'a' || key == 'A') user.updatePosition(user.currentRow, user.currentCol - 1);
  if (key == 'd' || key == 'D') user.updatePosition(user.currentRow, user.currentCol + 1);

  if (key == 'b' || key == 'B') user.tryBellHit();

  if (key == 't' || key == 'T') SHOW_TRAIL = !SHOW_TRAIL; //debugging
  if (key == 'm' || key == 'M') {
    fill(0, 0, 255);
    rect(0, 0, width, height);
  }
  if (key == 'l' || key == 'L') {
    outroScreen.nextStage();
  }
}


void displayLandingScreen() {
  background(210);

  color Black = color(25, 20, 20);
  color hotpink = color(240, 55, 165);
  float titleX = width * (1-0.12);
  float titleY = height * (0.20);

  float rightColumnX = width * 0.2;

  fill(Black);
  textAlign(RIGHT, TOP);
  textFont(helveticaNeueBold);
  textSize(width * 0.105);
  textLeading(width * 0.082);
  text("WHERE\nDO I\nGO?", titleX, titleY);

  textFont(helveticaNeueMedium);
  textSize(width * 0.012);
  textLeading(width * 0.015);
  textAlign(LEFT, TOP);
  text("A GAME-BASED\nEXPLORATION OF\nFAILURE AND\nPLAYFULNESS AS\nMUSICAL EXPRESSION", rightColumnX, height * (1-0.30));

  float startBaselineY = height * (1-0.69);
  float startSize = width * 0.026;
  float circleDiameter = startSize * 1.05;

  textFont(helveticaNeueBold);
  textSize(startSize);
  textAlign(LEFT, CENTER);
  fill(Black);

  text("START", rightColumnX, startBaselineY);

  float startWidth = textWidth("START");

  float arrowStartX = rightColumnX + startWidth + width * 0.012;
  float arrowEndX = arrowStartX + width * 0.035;

  stroke(Black);
  strokeWeight(3);

  line(arrowStartX, startBaselineY, arrowEndX, startBaselineY);
  line(arrowEndX, startBaselineY, arrowEndX - 10, startBaselineY - 7);
  line(arrowEndX, startBaselineY, arrowEndX - 10, startBaselineY + 7);

  float circleX = arrowEndX + width * 0.025 + circleDiameter / 2;

  fill(hotpink);
  stroke(0, 120);
  strokeWeight(2);
  ellipse(circleX, startBaselineY, cellSize/2, cellSize/2);


  // dashed outkine
  noFill();
  stroke(150);
  strokeWeight(3);
  float dashedR = 30;

  for (int i = 0; i < 15; i++) {
    float angleStart = TWO_PI * i / 15;
    float angleEnd = angleStart + 0.09;

    arc(circleX, startBaselineY,
      dashedR * 2, dashedR * 2,
      angleStart, angleEnd);
  }
}



void mousePressed() {
  if (showLanding) {
    float rightColumnX = width * 0.2;
    float startBaselineY = height * (1-0.69);

    boolean swissStart =
      mouseX > rightColumnX &&
      mouseX < rightColumnX + width * 0.20 &&
      mouseY > startBaselineY - 50 &&
      mouseY < startBaselineY + 50;

    if (swissStart) {
      showLanding = false;

      // Keep the Level 1 transition
      showingRoundScreen = true;
      roundScreenStartTime = millis();
      WAIT_FOR_MAX = false;
    }
  }
}
