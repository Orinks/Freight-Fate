// The iOS touch surface: one full-screen accessibility element over SDL's
// view, carrying the game's gesture recognizers.
//
// VoiceOver users meet a single element, "Freight Fate", that allows direct
// interaction, so the gestures below reach the game with VoiceOver on or
// off. The standard VoiceOver actions (double tap to activate, swipe up and
// down on an adjustable element, the two-finger scrub, the magic tap, the
// three-finger scroll) are answered too, for when direct touch is not
// active. Every gesture is queued as a small integer code; the Rust side
// (`touch.rs`) drains the queue each frame and turns the codes into the same
// key presses the desktop game reads. Speech never comes from here: Prism
// speaks through VoiceOver's announcement channel.

#import <UIKit/UIKit.h>
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
    FF_HOLD_UPPER_BEGAN = 14,
    FF_HOLD_LOWER_BEGAN = 15,
    FF_HOLD_ENDED = 16,
    FF_ESCAPE = 17,
    FF_MAGIC_TAP = 18,
    FF_ACTIVATE = 19,
    FF_INCREMENT = 20,
    FF_DECREMENT = 21,
    FF_THREE_FINGER_SWIPE_LEFT = 22,
    FF_THREE_FINGER_SWIPE_RIGHT = 23,
};

#define FF_QUEUE_CAPACITY 64

static int32_t ff_queue[FF_QUEUE_CAPACITY];
static unsigned ff_head = 0;
static unsigned ff_len = 0;
static os_unfair_lock ff_lock = OS_UNFAIR_LOCK_INIT;

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
        @"Swipe up or down to move, double tap to choose, scrub to go back. "
        @"Touch and hold the top half to accelerate, the bottom half to brake.";
    self.accessibilityTraits =
        UIAccessibilityTraitAllowsDirectInteraction | UIAccessibilityTraitAdjustable;
    [self installRecognizers];
    return self;
}

- (void)installRecognizers {
    UITapGestureRecognizer *threeDouble = [self tapWithTouches:3 taps:2 code:FF_THREE_FINGER_DOUBLE_TAP];
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

    UILongPressGestureRecognizer *hold =
        [[UILongPressGestureRecognizer alloc] initWithTarget:self action:@selector(held:)];
    hold.minimumPressDuration = 0.35;
    hold.numberOfTouchesRequired = 1;
    [self addGestureRecognizer:hold];
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

- (void)held:(UILongPressGestureRecognizer *)hold {
    switch (hold.state) {
    case UIGestureRecognizerStateBegan: {
        CGPoint at = [hold locationInView:self];
        ff_push(at.y < CGRectGetMidY(self.bounds) ? FF_HOLD_UPPER_BEGAN : FF_HOLD_LOWER_BEGAN);
        break;
    }
    case UIGestureRecognizerStateEnded:
    case UIGestureRecognizerStateCancelled:
    case UIGestureRecognizerStateFailed:
        ff_push(FF_HOLD_ENDED);
        break;
    default:
        break;
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
