// The iOS touch surface: one full-screen accessibility element over SDL's
// view, carrying the game's gesture recognizers.
//
// VoiceOver users meet a single element, "Freight Fate", that allows direct
// interaction, so the gestures below reach the game with VoiceOver on or
// off. The standard VoiceOver actions (double tap to activate, swipe up and
// down on an adjustable element, the two-finger scrub, the magic tap, the
// three-finger scroll) are answered too, for when direct touch is not
// active. Holding anywhere is gas; tap, then hold anywhere is brake, and a second finger
// tapping, double tapping or swiping while the pedal is held is a gesture of
// its own (hold gas to 20, tap with a second finger for cruise).
// Every gesture is queued as a small integer code; the Rust side
// (`touch.rs`) drains the queue each frame and hands each gesture to the
// game. Speech never comes from here: Prism speaks through VoiceOver's
// announcement channel.

#import <UIKit/UIKit.h>
#import <UIKit/UIGestureRecognizerSubclass.h>
#include <os/lock.h>
#include <stdint.h>

// Keep in step with `touch::Gesture::from_code`.
enum {
    FF_TAP = 0,
    FF_DOUBLE_TAP = 1,
    FF_SWIPE_UP = 2,
    FF_SWIPE_DOWN = 3,
    FF_SWIPE_LEFT = 4,
    FF_SWIPE_RIGHT = 5,
    FF_TWO_FINGER_TAP = 6,
    FF_TWO_FINGER_SWIPE_UP = 7,
    FF_TWO_FINGER_SWIPE_DOWN = 8,
    FF_TWO_FINGER_SWIPE_LEFT = 9,
    FF_TWO_FINGER_SWIPE_RIGHT = 10,
    FF_THREE_FINGER_SWIPE_UP = 11,
    FF_THREE_FINGER_SWIPE_DOWN = 12,
    FF_THREE_FINGER_DOUBLE_TAP = 13,
    FF_HOLD_UPPER_BEGAN = 14, // gas (saved code retained)
    FF_HOLD_LOWER_BEGAN = 15, // brake (saved code retained)
    FF_HOLD_ENDED = 16,
    FF_ESCAPE = 17,
    FF_MAGIC_TAP = 18,
    FF_ACTIVATE = 19,
    FF_INCREMENT = 20,
    FF_DECREMENT = 21,
    FF_THREE_FINGER_SWIPE_LEFT = 22,
    FF_THREE_FINGER_SWIPE_RIGHT = 23,
    FF_THREE_FINGER_TAP = 24,
    // A second finger while a pedal is held: the hold's base code plus one of
    // the FF_SECOND_* offsets below.
    FF_UPPER_HOLD_BASE = 25,
    FF_LOWER_HOLD_BASE = 31,
    FF_EMERGENCY_BRAKE_HOLD_BEGAN = 37,
    FF_HORN_HOLD_BEGAN = 38,
};

enum {
    FF_SECOND_TAP = 0,
    FF_SECOND_DOUBLE_TAP = 1,
    FF_SECOND_SWIPE_UP = 2,
    FF_SECOND_SWIPE_DOWN = 3,
    FF_SECOND_SWIPE_LEFT = 4,
    FF_SECOND_SWIPE_RIGHT = 5,
};

#define FF_QUEUE_CAPACITY 64

static int32_t ff_queue[FF_QUEUE_CAPACITY];
static unsigned ff_head = 0;
static unsigned ff_len = 0;
static os_unfair_lock ff_lock = OS_UNFAIR_LOCK_INIT;
static BOOL ff_haptics_enabled = YES;
static UIImpactFeedbackGenerator *ff_impact;
static UISelectionFeedbackGenerator *ff_selection;
static UINotificationFeedbackGenerator *ff_notification;

void ff_touch_set_haptics(int enabled) {
    ff_haptics_enabled = enabled != 0;
    if (!ff_impact) {
        ff_impact = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
        ff_selection = [[UISelectionFeedbackGenerator alloc] init];
        ff_notification = [[UINotificationFeedbackGenerator alloc] init];
    }
    [ff_impact prepare];
    [ff_selection prepare];
    [ff_notification prepare];
}

// kind: 0 light impact, 1 selection, 2 warning.
void ff_touch_haptic(int kind) {
    if (!ff_haptics_enabled) return;
    ff_touch_set_haptics(1);
    if (kind == 0) [ff_impact impactOccurred];
    else if (kind == 1) [ff_selection selectionChanged];
    else if (kind == 2) [ff_notification notificationOccurred:UINotificationFeedbackTypeWarning];
}

static void ff_push(int32_t code) {
    os_unfair_lock_lock(&ff_lock);
    if (ff_len == FF_QUEUE_CAPACITY) {
        // Drop the oldest: a stalled frame must not wedge the newest press.
        ff_head = (ff_head + 1) % FF_QUEUE_CAPACITY;
        ff_len--;
    }
    ff_queue[(ff_head + ff_len) % FF_QUEUE_CAPACITY] = code;
    ff_len++;
    os_unfair_lock_unlock(&ff_lock);
}

int32_t ff_touch_next(void) {
    int32_t code = -1;
    os_unfair_lock_lock(&ff_lock);
    if (ff_len > 0) {
        code = ff_queue[ff_head];
        ff_head = (ff_head + 1) % FF_QUEUE_CAPACITY;
        ff_len--;
    }
    os_unfair_lock_unlock(&ff_lock);
    return code;
}

// The pedals are location-independent. One finger held still is gas. A quick
// tap followed by a new touch down within FF_DOUBLE_TAP_SECONDS is brake.
// While either stays down, a second finger's taps and swipes are read here
// too, since the recognizer that owns the held touch is the one UIKit keeps
// feeding new touches to. A second tap waits FF_DOUBLE_TAP_SECONDS for a
// partner before it counts as a single tap, and a pending tap is sent before
// the pedal lets go, so "hold, tap, lift" runs the tap with the pedal down.

static const NSTimeInterval FF_HOLD_SECONDS = 0.35;
static const NSTimeInterval FF_DOUBLE_TAP_SECONDS = 0.28;
static const NSTimeInterval FF_SECOND_TAP_MAX_SECONDS = 0.4;
static const CGFloat FF_HOLD_SLOP = 12.0;
static const CGFloat FF_TAP_SLOP = 16.0;
static const CGFloat FF_SWIPE_DISTANCE = 36.0;

@interface FFPedalRecognizer : UIGestureRecognizer
@end

@implementation FFPedalRecognizer {
    UITouch *_pedal;
    CGPoint _pedalStart;
    int32_t _base;
    NSTimer *_holdTimer;
    UITouch *_second;
    CGPoint _secondStart;
    NSTimeInterval _secondStartTime;
    NSTimer *_tapTimer;
    NSTimeInterval _brakeArmedAt;
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    for (UITouch *touch in touches) {
        if (!_pedal) {
            _pedal = touch;
            _pedalStart = [touch locationInView:self.view];
            BOOL brake = _brakeArmedAt > 0 && touch.timestamp - _brakeArmedAt <= FF_DOUBLE_TAP_SECONDS;
            _brakeArmedAt = 0;
            _base = brake ? FF_LOWER_HOLD_BASE : FF_UPPER_HOLD_BASE;
            _holdTimer = [NSTimer scheduledTimerWithTimeInterval:FF_HOLD_SECONDS
                                                          target:self
                                                        selector:@selector(holdElapsed)
                                                        userInfo:nil
                                                         repeats:NO];
        } else if (self.state == UIGestureRecognizerStatePossible) {
            // Two fingers down together are a two-finger gesture, not a pedal.
            self.state = UIGestureRecognizerStateFailed;
            return;
        } else if (!_second) {
            _second = touch;
            _secondStart = [touch locationInView:self.view];
            _secondStartTime = touch.timestamp;
        }
    }
}

- (void)holdElapsed {
    _holdTimer = nil;
    if (self.state != UIGestureRecognizerStatePossible || !_pedal) {
        return;
    }
    ff_push(_base == FF_UPPER_HOLD_BASE ? FF_HOLD_UPPER_BEGAN : FF_HOLD_LOWER_BEGAN);
    ff_touch_haptic(0);
    self.state = UIGestureRecognizerStateBegan;
}

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.state == UIGestureRecognizerStatePossible && [touches containsObject:_pedal]) {
        CGPoint at = [_pedal locationInView:self.view];
        if (hypot(at.x - _pedalStart.x, at.y - _pedalStart.y) > FF_HOLD_SLOP) {
            self.state = UIGestureRecognizerStateFailed;
        }
    }
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (_second && [touches containsObject:_second]) {
        [self secondLifted:_second];
        _second = nil;
    }
    if ([touches containsObject:_pedal]) {
        if (self.state == UIGestureRecognizerStatePossible) {
            _brakeArmedAt = ((UITouch *)[touches anyObject]).timestamp;
        }
        [self pedalLifted:UIGestureRecognizerStateEnded];
    }
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (_second && [touches containsObject:_second]) {
        _second = nil;
    }
    if ([touches containsObject:_pedal]) {
        [self pedalLifted:UIGestureRecognizerStateCancelled];
    }
}

- (void)pedalLifted:(UIGestureRecognizerState)how {
    if (self.state == UIGestureRecognizerStatePossible) {
        self.state = UIGestureRecognizerStateFailed;
        return;
    }
    [self flushPendingTap];
    ff_push(FF_HOLD_ENDED);
    ff_touch_haptic(0);
    self.state = how;
}

- (void)secondLifted:(UITouch *)touch {
    if (self.state != UIGestureRecognizerStateBegan && self.state != UIGestureRecognizerStateChanged) {
        return;
    }
    CGPoint at = [touch locationInView:self.view];
    CGFloat dx = at.x - _secondStart.x;
    CGFloat dy = at.y - _secondStart.y;
    CGFloat distance = hypot(dx, dy);
    if (distance >= FF_SWIPE_DISTANCE) {
        [self flushPendingTap];
        int32_t offset;
        if (fabs(dx) > fabs(dy)) {
            offset = dx > 0 ? FF_SECOND_SWIPE_RIGHT : FF_SECOND_SWIPE_LEFT;
        } else {
            offset = dy > 0 ? FF_SECOND_SWIPE_DOWN : FF_SECOND_SWIPE_UP;
        }
        ff_push(_base + offset);
        ff_touch_haptic(1);
    } else if (distance <= FF_TAP_SLOP && touch.timestamp - _secondStartTime <= FF_SECOND_TAP_MAX_SECONDS) {
        if (_tapTimer) {
            [_tapTimer invalidate];
            _tapTimer = nil;
            ff_push(_base + FF_SECOND_DOUBLE_TAP);
            ff_touch_haptic(1);
        } else {
            _tapTimer = [NSTimer scheduledTimerWithTimeInterval:FF_DOUBLE_TAP_SECONDS
                                                         target:self
                                                       selector:@selector(tapElapsed)
                                                       userInfo:nil
                                                        repeats:NO];
        }
    } else {
        return;
    }
    self.state = UIGestureRecognizerStateChanged;
}

- (void)tapElapsed {
    _tapTimer = nil;
    ff_push(_base + FF_SECOND_TAP);
    ff_touch_haptic(1);
}

- (void)flushPendingTap {
    if (_tapTimer) {
        [_tapTimer invalidate];
        [self tapElapsed];
    }
}

- (void)reset {
    [super reset];
    [_holdTimer invalidate];
    _holdTimer = nil;
    [_tapTimer invalidate];
    _tapTimer = nil;
    _pedal = nil;
    _second = nil;
}

@end

@interface FFTouchView : UIView
@end

@implementation FFTouchView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (!self) {
        return nil;
    }
    self.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.backgroundColor = UIColor.clearColor;
    self.multipleTouchEnabled = YES;
    self.isAccessibilityElement = YES;
    self.accessibilityLabel = @"Freight Fate";
    self.accessibilityHint =
        @"Hold anywhere for gas, tap then hold to brake. Swipe and tap anywhere for commands.";
    self.accessibilityTraits =
        UIAccessibilityTraitAllowsDirectInteraction | UIAccessibilityTraitAdjustable;
    if (@available(iOS 17.0, *)) {
        self.accessibilityDirectTouchOptions = UIAccessibilityDirectTouchOptionSilentOnTouch;
    }
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(voiceOverChanged:)
                                                 name:UIAccessibilityVoiceOverStatusDidChangeNotification
                                               object:nil];
    [self installRecognizers];
    return self;
}

- (void)installRecognizers {
    UITapGestureRecognizer *threeDouble = [self tapWithTouches:3 taps:2 code:FF_THREE_FINGER_DOUBLE_TAP];
    UITapGestureRecognizer *threeSingle = [self tapWithTouches:3 taps:1 code:FF_THREE_FINGER_TAP];
    [threeSingle requireGestureRecognizerToFail:threeDouble];
    UITapGestureRecognizer *twoDouble = [self tapWithTouches:2 taps:2 code:FF_MAGIC_TAP];
    UITapGestureRecognizer *twoSingle = [self tapWithTouches:2 taps:1 code:FF_TWO_FINGER_TAP];
    [twoSingle requireGestureRecognizerToFail:twoDouble];
    UITapGestureRecognizer *oneDouble = [self tapWithTouches:1 taps:2 code:FF_DOUBLE_TAP];
    UITapGestureRecognizer *oneSingle = [self tapWithTouches:1 taps:1 code:FF_TAP];
    [oneSingle requireGestureRecognizerToFail:oneDouble];
    (void)threeDouble;

    const struct {
        NSUInteger touches;
        UISwipeGestureRecognizerDirection direction;
        int32_t code;
    } swipes[] = {
        {1, UISwipeGestureRecognizerDirectionUp, FF_SWIPE_UP},
        {1, UISwipeGestureRecognizerDirectionDown, FF_SWIPE_DOWN},
        {1, UISwipeGestureRecognizerDirectionLeft, FF_SWIPE_LEFT},
        {1, UISwipeGestureRecognizerDirectionRight, FF_SWIPE_RIGHT},
        {2, UISwipeGestureRecognizerDirectionUp, FF_TWO_FINGER_SWIPE_UP},
        {2, UISwipeGestureRecognizerDirectionDown, FF_TWO_FINGER_SWIPE_DOWN},
        {2, UISwipeGestureRecognizerDirectionLeft, FF_TWO_FINGER_SWIPE_LEFT},
        {2, UISwipeGestureRecognizerDirectionRight, FF_TWO_FINGER_SWIPE_RIGHT},
        {3, UISwipeGestureRecognizerDirectionUp, FF_THREE_FINGER_SWIPE_UP},
        {3, UISwipeGestureRecognizerDirectionDown, FF_THREE_FINGER_SWIPE_DOWN},
        {3, UISwipeGestureRecognizerDirectionLeft, FF_THREE_FINGER_SWIPE_LEFT},
        {3, UISwipeGestureRecognizerDirectionRight, FF_THREE_FINGER_SWIPE_RIGHT},
    };
    for (size_t i = 0; i < sizeof(swipes) / sizeof(swipes[0]); i++) {
        UISwipeGestureRecognizer *swipe =
            [[UISwipeGestureRecognizer alloc] initWithTarget:self action:@selector(swiped:)];
        swipe.numberOfTouchesRequired = swipes[i].touches;
        swipe.direction = swipes[i].direction;
        [swipe setValue:@(swipes[i].code) forKey:@"ffCode"];
        [self addGestureRecognizer:swipe];
    }

    FFPedalRecognizer *pedal = [[FFPedalRecognizer alloc] initWithTarget:nil action:nil];
    [oneSingle requireGestureRecognizerToFail:pedal];
    [self addGestureRecognizer:pedal];
    [self addHoldWithTouches:2 code:FF_EMERGENCY_BRAKE_HOLD_BEGAN magicTap:twoDouble];
    [self addHoldWithTouches:3 code:FF_HORN_HOLD_BEGAN magicTap:twoDouble];
}

- (void)addHoldWithTouches:(NSUInteger)touches code:(int32_t)code magicTap:(UITapGestureRecognizer *)magicTap {
    UILongPressGestureRecognizer *hold = [[UILongPressGestureRecognizer alloc] initWithTarget:self action:@selector(held:)];
    hold.numberOfTouchesRequired = touches;
    hold.minimumPressDuration = FF_HOLD_SECONDS;
    hold.allowableMovement = FF_HOLD_SLOP;
    [hold setValue:@(code) forKey:@"ffCode"];
    [hold requireGestureRecognizerToFail:magicTap];
    [self addGestureRecognizer:hold];
}

- (void)held:(UILongPressGestureRecognizer *)hold {
    if (hold.state == UIGestureRecognizerStateBegan) {
        ff_push([[hold valueForKey:@"ffCode"] intValue]);
        ff_touch_haptic([[hold valueForKey:@"ffCode"] intValue] == FF_EMERGENCY_BRAKE_HOLD_BEGAN ? 2 : 0);
    } else if (hold.state == UIGestureRecognizerStateEnded || hold.state == UIGestureRecognizerStateCancelled) {
        ff_push(FF_HOLD_ENDED);
        ff_touch_haptic(0);
    }
}

- (void)voiceOverChanged:(NSNotification *)notification {
    UIAccessibilityPostNotification(UIAccessibilityScreenChangedNotification, self);
}

- (UITapGestureRecognizer *)tapWithTouches:(NSUInteger)touches taps:(NSUInteger)taps code:(int32_t)code {
    UITapGestureRecognizer *tap =
        [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(tapped:)];
    tap.numberOfTouchesRequired = touches;
    tap.numberOfTapsRequired = taps;
    [tap setValue:@(code) forKey:@"ffCode"];
    [self addGestureRecognizer:tap];
    return tap;
}

- (void)tapped:(UITapGestureRecognizer *)tap {
    if (tap.state == UIGestureRecognizerStateEnded) {
        ff_push([[tap valueForKey:@"ffCode"] intValue]);
    }
}

- (void)swiped:(UISwipeGestureRecognizer *)swipe {
    if (swipe.state == UIGestureRecognizerStateEnded) {
        ff_push([[swipe valueForKey:@"ffCode"] intValue]);
    }
}

- (BOOL)accessibilityActivate {
    ff_push(FF_ACTIVATE);
    return YES;
}

- (void)accessibilityIncrement {
    ff_push(FF_INCREMENT);
}

- (void)accessibilityDecrement {
    ff_push(FF_DECREMENT);
}

- (BOOL)accessibilityPerformEscape {
    ff_push(FF_ESCAPE);
    return YES;
}

- (BOOL)accessibilityPerformMagicTap {
    ff_push(FF_MAGIC_TAP);
    return YES;
}

- (BOOL)accessibilityScroll:(UIAccessibilityScrollDirection)direction {
    switch (direction) {
    case UIAccessibilityScrollDirectionLeft:
        ff_push(FF_THREE_FINGER_SWIPE_LEFT);
        return YES;
    case UIAccessibilityScrollDirectionRight:
        ff_push(FF_THREE_FINGER_SWIPE_RIGHT);
        return YES;
    case UIAccessibilityScrollDirectionUp:
        ff_push(FF_THREE_FINGER_SWIPE_UP);
        return YES;
    case UIAccessibilityScrollDirectionDown:
        ff_push(FF_THREE_FINGER_SWIPE_DOWN);
        return YES;
    default:
        return NO;
    }
}

@end

// The recognizers carry their gesture code as an associated value.
#import <objc/runtime.h>

static const void *FF_CODE_KEY = &FF_CODE_KEY;

@interface UIGestureRecognizer (FFCode)
@end

@implementation UIGestureRecognizer (FFCode)
- (void)setFfCode:(NSNumber *)code {
    objc_setAssociatedObject(self, FF_CODE_KEY, code, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}
- (NSNumber *)ffCode {
    return objc_getAssociatedObject(self, FF_CODE_KEY);
}
@end

// Lay the touch surface over SDL's view. `window` is the UIWindow SDL made
// (what its window-manager info reports); a UIView is accepted as well.
// Returns 1 when the surface is in place.
int32_t ff_touch_install(void *window) {
    if (!window) {
        return 0;
    }
    id object = (__bridge id)window;
    UIView *host = nil;
    if ([object isKindOfClass:[UIWindow class]]) {
        UIWindow *ui_window = (UIWindow *)object;
        host = ui_window.rootViewController.view ?: ui_window;
    } else if ([object isKindOfClass:[UIView class]]) {
        host = (UIView *)object;
    }
    if (!host) {
        return 0;
    }
    FFTouchView *surface = [[FFTouchView alloc] initWithFrame:host.bounds];
    [host addSubview:surface];
    UIAccessibilityPostNotification(UIAccessibilityScreenChangedNotification, surface);
    return 1;
}
