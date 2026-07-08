// Asteroids.js
// Copyright (c) 2010–2023 James Socol <me@jamessocol.com> + AI
// See LICENSE.txt for license terms.

// Game settings
GAME_HEIGHT = 480; // Replaced at startup: the game fills the window.
GAME_WIDTH = 640;
FRAME_PERIOD = 60; // 1 frame / x frames/sec
LEVEL_TIMEOUT = 2000; // How long to wait after clearing a level.

// Player settings
ROTATE_SPEED = Math.PI / 10; // How fast do players turn?  (radians)
MAX_SPEED = 15; // Maximum player speed
THRUST_ACCEL = 1;
BRAKE_POWER = 0.06; // Fraction of speed shed per frame while braking.
DEATH_TIMEOUT = 2000; // milliseconds
INVINCIBLE_TIMEOUT = 1500; // How long to stay invincible after resurrecting?
PLAYER_LIVES = 3;
POINTS_PER_SHOT = 1; // How many points does a shot cost? (Should be >= 0.)
POINTS_TO_EXTRA_LIFE = 10000; // How many points to get a 1-up?
HYPERSPACE_ENABLED = false; // Set true to allow hyperspace jumps.
HYPERSPACE_TIME = 600; // How long a hyperspace jump takes. (ms)
HYPERSPACE_RISK = 1 / 6; // Chance that hyperspace destroys the ship.

// Bullet settings
BULLET_SPEED = 20;
MAX_BULLETS = 3;
MAX_BULLET_AGE = 25;
AMMO_LIMIT = 100; // Shots per level; refills when a new level starts.

// Saucer settings
SAUCER_TIME = 12000; // Rough time between saucer visits. (ms)
SAUCER_SPEED = 2.5;
SAUCER_FIRE_TIME = 1400; // Time between saucer shots. (ms)
SAUCER_BULLET_AGE = 40;
SAUCER_SCORE_BIG = 200;
SAUCER_SCORE_SMALL = 1000;
SAUCER_AIM_ERROR = 0.4; // The small saucer's aim error at level 1. (radians)
SAUCER_BIG_AIM_ERROR = 2.5; // The big saucer's aim error, relative to the small one.
FRIENDLY_FIRE_AGE = 4; // Frames before a bullet can hit its own shooter.

// Asteroid settings
ASTEROID_COUNT = 3; // This + current level = number of asteroids...
MAX_ASTEROIDS = 11; // ...but no more than this many to start a level.
ASTEROID_GENERATIONS = 3; // How many times to they split before dying?
ASTEROID_CHILDREN = 2; // How many does each death create?
ASTEROID_SPEED = 3;
ASTEROID_SCORES = [0, 100, 50, 20]; // Points by generation; small rocks pay best.
SAFE_SPAWN_DISTANCE = 100; // How close to the player new rocks may spawn. (px)


var Asteroids = function (home, startMode) {
    // Constructor
    // Order matters.

    // Set up logging.
    this.log_level = Asteroids.LOG_DEBUG;
    this.log = Asteroids.logger(this);

    // Create the info pane, player, and playfield.
    home.innerHTML = '';
    this.home = home;
    this.startMode = startMode || 'attract'; // 'attract' or 'playing'.
    this.cleanups = []; // Teardown functions, run before a restart.

    // Sound effects (a singleton, shared across restarts).
    this.sound = Asteroids.sound();
    var sound = this.sound;
    this.cleanups.push(function () {
        sound.thrust(false);
        sound.saucer(false);
    });

    this.info = Asteroids.infoPane(this, home);
    this.playfield = Asteroids.playfield(this, home);
    this.player = Asteroids.player(this);

    // Set up the event listeners.
    this.keyState = Asteroids.keyState(this);
    this.listen = Asteroids.listen(this);

    // Touch controls on mobile, keyboard instructions otherwise.
    this.controls = Asteroids.controls(this, home);

    // Useful functions.
    this.asteroids = Asteroids.asteroids(this);
    this.overlays = Asteroids.overlays(this);
    this.highScores = Asteroids.highScores(this);
    this.level = Asteroids.level(this);
    this.gameOver = Asteroids.gameOver(this);

    // Play the game.
    Asteroids.play(this);
    return this;
}

Asteroids.infoPane = function (game, home) {
    var pane = document.createElement('div');

    var back = document.createElement('a');
    back.className = 'back-btn';
    back.href = '../';
    back.title = 'Back to schedule';
    back.innerHTML = '&larr;';
    pane.appendChild(back);

    pane.appendChild(document.createTextNode(' ASTEROIDS'));

    var lives = document.createElement('span');
    lives.className = 'lives';
    lives.innerHTML = 'LIVES: ' + PLAYER_LIVES;

    var score = document.createElement('span');
    score.className = 'score';
    score.innerHTML = 'SCORE: 0';

    var level = document.createElement('span');
    level.className = 'level';
    level.innerHTML = 'LEVEL: 1';

    var ammo = document.createElement('span');
    ammo.className = 'ammo';
    ammo.innerHTML = 'AMMO: ' + AMMO_LIMIT;

    pane.appendChild(lives);
    pane.appendChild(score);
    pane.appendChild(ammo);
    pane.appendChild(level);

    if (Asteroids.isMobile()) {
        var pause = document.createElement('span');
        pause.className = 'pause-btn';
        pause.innerHTML = 'PAUSE';

        pause.addEventListener('touchstart', function (e) {
            e.preventDefault();
            game.sound.unlock();
            Asteroids.togglePause(game);
            pause.innerHTML = game.paused ? 'RESUME' : 'PAUSE';
        });

        pane.appendChild(pause);
    }

    home.appendChild(pane);

    return {
        setLives: function (game, l) {
            lives.innerHTML = 'LIVES: ' + l;
        },
        setScore: function (game, s) {
            score.innerHTML = 'SCORE: ' + s;
        },
        setLevel: function (game, _level) {
            level.innerHTML = 'LEVEL: ' + _level;
        },
        setAmmo: function (game, a) {
            ammo.innerHTML = 'AMMO: ' + a;
        },
        getPane: function () {
            return pane;
        }
    }
}

Asteroids.playfield = function (game, home) {
    var canvas = document.createElement('canvas');
    home.appendChild(canvas);

    // Fill all the space the page gives the canvas, and keep the
    // game field in sync with it.
    var resize = function () {
        GAME_WIDTH = canvas.width = canvas.clientWidth;
        GAME_HEIGHT = canvas.height = canvas.clientHeight;

        // Setting the canvas size resets the drawing context.
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = 'white';
        ctx.strokeStyle = 'white';
    };
    resize();
    window.addEventListener('resize', resize);
    game.cleanups.push(function () {
        window.removeEventListener('resize', resize);
    });

    return canvas;
}

Asteroids.logger = function (game) {
    if (typeof console != 'undefined' &&
        typeof console.log != 'undefined') {
        return {
            info: function (msg) {
                if (game.log_level <= Asteroids.LOG_INFO)
                    console.log(msg);
            },
            debug: function (msg) {
                if (game.log_level <= Asteroids.LOG_DEBUG)
                    console.log(msg);
            },
            warning: function (msg) {
                if (game.log_level <= Asteroids.LOG_WARNING)
                    console.log(msg);
            },
            error: function (msg) {
                if (game.log_level <= Asteroids.LOG_ERROR)
                    console.log(msg);
            },
            critical: function (msg) {
                if (game.log_level <= Asteroids.LOG_CRITICAL)
                    console.log(msg);
            }
        }
    }
    else {
        return {
            info: function (msg) { },
            debug: function (msg) { },
            warning: function (msg) { },
            error: function (msg) { },
            critical: function (msg) { },
        }
    }
}

Asteroids.asteroids = function (game) {
    var asteroids = [];

    return {
        push: function (obj) {
            return asteroids.push(obj);
        },
        pop: function () {
            return asteroids.pop();
        },
        splice: function (i, j) {
            return asteroids.splice(i, j);
        },
        get length() {
            return asteroids.length;
        },
        getIterator: function () {
            return asteroids;
        },
        generationCount: function (_gen) {
            var total = 0;
            for (var i = 0; i < asteroids.length; i++) {
                if (asteroids[i].getGeneration() == _gen)
                    total++;
            }
            game.log.debug('Found ' + total + ' asteroids in generation ' +
                _gen);
            return total;
        }
    }
}

/**
 * Creates an overlays controller.
 */
Asteroids.overlays = function (game) {
    var overlays = [];

    return {
        draw: function (ctx) {
            for (var i = 0; i < overlays.length; i++) {
                overlays[i].draw(ctx);
            }
        },
        add: function (obj) {
            if (-1 == overlays.indexOf(obj) &&
                typeof obj.draw != 'undefined') {
                overlays.push(obj);
                return true;
            }
            return false;
        },
        remove: function (obj) {
            var i = overlays.indexOf(obj);
            if (-1 != i) {
                overlays.splice(i, 1);
                return true;
            }
            return false;
        }
    }
}

/**
 * Creates a player object.
 */
Asteroids.player = function (game) {
    // implements IScreenObject
    var position = [GAME_WIDTH / 2, GAME_HEIGHT / 2],
        velocity = [0, 0],
        direction = -Math.PI / 2,
        dead = false,
        invincible = false,
        hyper = false, // In hyperspace right now?
        lastThrust = 0,
        lastRez = null,
        lives = PLAYER_LIVES,
        score = 0,
        ammo = AMMO_LIMIT,
        radius = 3,
        path = [
            [10, 0],
            [-5, 5],
            [-5, -5],
            [10, 0],
        ];

    return {
        getPosition: function () {
            return position;
        },
        getVelocity: function () {
            return velocity;
        },
        getSpeed: function () {
            return Math.sqrt(Math.pow(velocity[0], 2) + Math.pow(velocity[1], 2));
        },
        getDirection: function () {
            return direction;
        },
        getRadius: function () {
            return radius;
        },
        getWorldPath: function () {
            return Asteroids.worldPath(path, position, direction, 1);
        },
        getScore: function () {
            return score;
        },
        addScore: function (pts) {
            score += pts;
        },
        lowerScore: function (pts) {
            score -= pts;
            if (score < 0) {
                score = 0;
            }
        },
        getLives: function () {
            return lives;
        },
        getAmmo: function () {
            return ammo;
        },
        resetAmmo: function () {
            ammo = AMMO_LIMIT;
        },
        rotate: function (rad) {
            if (!dead && !hyper) {
                direction += rad;
                game.log.info(direction);
            }
        },
        thrust: function (force) {
            if (!dead && !hyper) {
                lastThrust = Date.now();
                velocity[0] += force * Math.cos(direction);
                velocity[1] += force * Math.sin(direction);

                if (this.getSpeed() > MAX_SPEED) {
                    velocity[0] = MAX_SPEED * Math.cos(direction);
                    velocity[1] = MAX_SPEED * Math.sin(direction);
                }

                game.log.info(velocity);
            }
        },
        brake: function (factor) {
            if (!dead && !hyper) {
                velocity[0] *= (1 - factor);
                velocity[1] *= (1 - factor);
            }
        },
        move: function () {
            Asteroids.move(position, velocity);
        },
        draw: function (ctx) {
            let color = '#fff';
            if (invincible) {
                const dt = ((new Date) - lastRez) / 200;
                const c = Math.floor(Math.abs(Math.cos(dt)) * 15).toString(16);
                color = `#${c}${c}${c}`;
            }
            Asteroids.drawPath(ctx, position, direction, 1, path, color);

            // Show a flickering exhaust flame while under thrust.
            if (this.isThrusting() && Math.random() < 0.7) {
                const flame = [
                    [-5, -3],
                    [-8 - Math.random() * 4, 0],
                    [-5, 3],
                ];
                Asteroids.drawPath(ctx, position, direction, 1, flame, color);
            }
        },
        isDead: function () {
            return dead;
        },
        isInvincible: function () {
            return invincible;
        },
        isHyper: function () {
            return hyper;
        },
        isThrusting: function () {
            return (Date.now() - lastThrust) < 120;
        },
        hyperspace: function (game) {
            // Vanish, then reappear somewhere random -- if you're lucky.
            if (dead || hyper)
                return;
            game.log.debug('Hyperspace!');
            hyper = true;
            game.sound.hyperspace();
            var self = this;
            setTimeout(function () {
                position[0] = Math.random() * GAME_WIDTH;
                position[1] = Math.random() * GAME_HEIGHT;
                velocity[0] = 0;
                velocity[1] = 0;
                hyper = false;
                if (Math.random() < HYPERSPACE_RISK)
                    self.die(game);
            }, HYPERSPACE_TIME);
        },
        extraLife: function (game) {
            game.log.debug('Woo, extra life!');
            lives++;
        },
        die: function (game) {
            if (!dead) {
                game.log.info('You died!');
                game.sound.explosion(4);
                dead = true;
                invincible = true;
                lives--;
                position = [GAME_WIDTH / 2, GAME_HEIGHT / 2];
                velocity = [0, 0];
                direction = -Math.PI / 2;
                if (lives > 0) {
                    setTimeout(function (player, _game) {
                        return function () {
                            player.resurrect(_game);
                        }
                    }(this, game), DEATH_TIMEOUT);
                }
                else {
                    game.gameOver();
                }
            }
        },
        resurrect: function (game) {
            if (dead) {
                dead = false;
                invincible = true;
                lastRez = new Date;
                setTimeout(function () {
                    invincible = false;
                    game.log.debug('No longer invincible!');
                }, INVINCIBLE_TIMEOUT);
                game.log.debug('You ressurrected!');
            }
        },
        fire: function (game) {
            if (!dead && !hyper && ammo > 0) {
                game.log.debug('You fired!');
                var _pos = [position[0], position[1]],
                    _dir = direction;

                ammo--;
                this.lowerScore(POINTS_PER_SHOT);

                return Asteroids.bullet(game, _pos, _dir);
            }
        }
    }
}

Asteroids.bullet = function (game, _pos, _dir, _saucer) {
    // implements IScreenObject
    var position = [_pos[0], _pos[1]],
        velocity = [0, 0],
        direction = _dir,
        age = 0,
        radius = _saucer ? 2 : 1,
        path = [
            [0, 0],
            [-4, 0],
        ];

    velocity[0] = BULLET_SPEED * Math.cos(_dir);
    velocity[1] = BULLET_SPEED * Math.sin(_dir);

    return {
        getPosition: function () {
            return position;
        },
        getLastPosition: function () {
            // Where the bullet was before this frame's move; collision
            // tests sweep the segment between the two so fast bullets
            // can't skip through things.
            return [position[0] - velocity[0], position[1] - velocity[1]];
        },
        getVelocity: function () {
            return velocity;
        },
        getSpeed: function () {
            return Math.sqrt(Math.pow(velocity[0], 2) + Math.pow(velocity[1], 2));
        },
        getRadius: function () {
            return radius;
        },
        getAge: function () {
            return age;
        },
        birthday: function () {
            age++;
        },
        move: function () {
            Asteroids.move(position, velocity);
        },
        draw: function (ctx) {
            if (_saucer) {
                // Saucer shots are little circles.
                ctx.setTransform(1, 0, 0, 1, position[0], position[1]);
                ctx.beginPath();
                ctx.arc(0, 0, radius, 0, Math.PI * 2, false);
                ctx.fill();
            }
            else {
                Asteroids.drawPath(ctx, position, direction, 1, path);
            }
        },
    }
}

/**
 * Creates a flying saucer. Big ones wander across the field shooting
 * at random; small ones are faster, worth more, and shoot at you.
 */
Asteroids.saucer = function (game, small) {
    // implements IScreenObject
    var fromLeft = Math.random() < 0.5,
        radius = small ? 10 : 16,
        position = [fromLeft ? -20 : GAME_WIDTH + 20,
        Math.random() * GAME_HEIGHT],
        velocity = [(small ? SAUCER_SPEED * 1.4 : SAUCER_SPEED) *
            (fromLeft ? 1 : -1), 0],
        nextTurn = Date.now(),
        nextShot = Date.now() + SAUCER_FIRE_TIME;

    return {
        getPosition: function () {
            return position;
        },
        getRadius: function () {
            return radius;
        },
        isSmall: function () {
            return small;
        },
        getScore: function () {
            return small ? SAUCER_SCORE_SMALL : SAUCER_SCORE_BIG;
        },
        isGone: function () {
            // Saucers cross the field once and leave.
            return fromLeft ? position[0] > GAME_WIDTH + 30 :
                position[0] < -30;
        },
        update: function (now) {
            // Zigzag now and then.
            if (now > nextTurn) {
                velocity[1] = (Math.floor(Math.random() * 3) - 1) *
                    Math.abs(velocity[0]) * 0.8;
                nextTurn = now + 700 + Math.random() * 1300;
            }

            position[0] += velocity[0];
            position[1] += velocity[1];
            if (position[1] < 0)
                position[1] += GAME_HEIGHT;
            else if (position[1] > GAME_HEIGHT)
                position[1] -= GAME_HEIGHT;

            // Take a shot when it's time. Both saucers aim at the
            // player -- the big one sloppily -- and their aim
            // sharpens at higher levels.
            if (game.mode == 'playing' && !game.player.isDead() &&
                now > nextShot) {
                nextShot = now + SAUCER_FIRE_TIME;
                var p = game.player.getPosition(),
                    error = SAUCER_AIM_ERROR *
                        (small ? 1 : SAUCER_BIG_AIM_ERROR) /
                        (1 + game.level.getLevel() / 2),
                    dir = Math.atan2(p[1] - position[1],
                        p[0] - position[0]) +
                        (Math.random() - 0.5) * 2 * error;
                return Asteroids.bullet(game,
                    [position[0], position[1]], dir, true);
            }
            return null;
        },
        draw: function (ctx) {
            ctx.save();
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.font = 'bold ' + (small ? 16 : 24) + 'px System, monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#fff';
            ctx.fillText('SPIE', position[0], position[1]);
            ctx.restore();
        }
    }
}

Asteroids.keyState = function (_) {
    var state = {
        [Asteroids.LEFT]: false,
        [Asteroids.UP]: false,
        [Asteroids.RIGHT]: false,
        [Asteroids.DOWN]: false,
        [Asteroids.HYPER]: false,
        [Asteroids.FIRE]: false
    };

    return {
        on: function (key) {
            state[key] = true;
        },
        off: function (key) {
            state[key] = false;
        },
        getState: function (key) {
            if (typeof state[key] != 'undefined')
                return state[key];
            return false;
        }
    }
}

Asteroids.listen = function (game) {
    const keyMap = {
        "ArrowLeft": Asteroids.LEFT,
        "KeyA": Asteroids.LEFT,
        "ArrowRight": Asteroids.RIGHT,
        "KeyD": Asteroids.RIGHT,
        "ArrowUp": Asteroids.UP,
        "KeyW": Asteroids.UP,
        "ArrowDown": Asteroids.DOWN,
        "KeyS": Asteroids.DOWN,
        "ShiftLeft": Asteroids.HYPER,
        "ShiftRight": Asteroids.HYPER,
        "Space": Asteroids.FIRE
    };

    const keydown = function (e) {
        // Leave the high-score initials form alone.
        if (e.target.tagName == 'INPUT')
            return true;

        // Any keypress is a chance to unlock the audio context.
        game.sound.unlock();

        if (e.code == 'KeyP' && !e.repeat) {
            Asteroids.togglePause(game);
            return true;
        }

        if (e.code == 'KeyM' && !e.repeat) {
            game.sound.toggleMute();
            return true;
        }

        const state = keyMap[e.code];
        if (state) {
            e.preventDefault();
            e.stopPropagation();
            game.keyState.on(state);
            return false;
        }
        return true;
    };

    const keyup = function (e) {
        if (e.target.tagName == 'INPUT')
            return true;

        const state = keyMap[e.code];
        if (state) {
            e.preventDefault();
            e.stopPropagation();
            game.keyState.off(state);
            return false;
        }
        return true;
    };

    // Pause when the tab goes into the background.
    const hidden = function () {
        if (document.hidden && game.mode == 'playing' && !game.paused)
            Asteroids.togglePause(game);
    };

    window.addEventListener('keydown', keydown, true);
    window.addEventListener('keyup', keyup, true);
    document.addEventListener('visibilitychange', hidden);
    game.cleanups.push(function () {
        window.removeEventListener('keydown', keydown, true);
        window.removeEventListener('keyup', keyup, true);
        document.removeEventListener('visibilitychange', hidden);
    });
}

/**
 * Pauses or resumes a running game.
 */
Asteroids.togglePause = function (game) {
    if (game.mode != 'playing')
        return;

    game.paused = !game.paused;
    game.log.debug(game.paused ? 'Paused.' : 'Resumed.');

    // Quiet the looping sounds; they restart on the next frame.
    game.sound.thrust(false);
    game.sound.saucer(false);

    if (game.paused) {
        var ctx = game.playfield.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.font = '30px System, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('PAUSED', GAME_WIDTH / 2, GAME_HEIGHT / 2);
    }
}

Asteroids.isMobile = function () {
    if (typeof Asteroids._isMobile == 'undefined') {
        Asteroids._isMobile =
            (typeof window.matchMedia != 'undefined' &&
                window.matchMedia('(hover: none) and (pointer: coarse)').matches) ||
            'ontouchstart' in window && navigator.maxTouchPoints > 0 &&
            /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    }
    return Asteroids._isMobile;
}

Asteroids.controls = function (game, home) {
    if (!Asteroids.isMobile()) {
        // Desktop: just show the keyboard controls.
        var help = document.createElement('div');
        help.className = 'keyboard-help';
        help.innerHTML = 'CONTROLS: &larr; &rarr; or A/D turn &nbsp;&middot;&nbsp; ' +
            '&uarr; or W thrust &nbsp;&middot;&nbsp; ' +
            'S or &darr; brake &nbsp;&middot;&nbsp; SPACE fire ' +
            (HYPERSPACE_ENABLED ?
                '&nbsp;&middot;&nbsp; SHIFT hyperspace ' : '') +
            '&nbsp;&middot;&nbsp; P pause ' +
            '&nbsp;&middot;&nbsp; M sound on/off';
        home.appendChild(help);
        return;
    }

    var controls = document.createElement('div');
    controls.className = 'touch-controls';

    var pad = document.createElement('div');
    pad.className = 'joystick';

    var knob = document.createElement('div');
    knob.className = 'knob';
    pad.appendChild(knob);

    var fire = document.createElement('div');
    fire.className = 'fire-button';
    fire.innerHTML = '<span>FIRE</span>';

    var buttons = document.createElement('div');
    buttons.className = 'buttons';

    var hyper = document.createElement('div');
    if (HYPERSPACE_ENABLED) {
        hyper.className = 'hyper-button';
        hyper.innerHTML = '<span>HYPER</span>';
        buttons.appendChild(hyper);
    }
    buttons.appendChild(fire);

    controls.appendChild(pad);
    controls.appendChild(buttons);
    home.appendChild(controls);

    // Joystick: the ship turns toward the direction the stick is
    // pushed, and its speed follows how far the stick is pushed —
    // full deflection is full speed, centered is a standstill. The
    // knob follows the finger so you can see direction and strength.
    var DEADZONE = 0.15, // fraction of full deflection to ignore
        SPEED_EASING = 0.1, // how fast speed approaches the stick's, per frame
        padTouch = null, // identifier of the finger on the stick
        stick = [0, 0], // deflection on each axis, in [-1, 1]
        trackStick = function (t) {
            var rect = pad.getBoundingClientRect(),
                radius = rect.width / 2,
                dx = (t.clientX - rect.left - radius) / radius,
                dy = (t.clientY - rect.top - radius) / radius,
                mag = Math.sqrt(dx * dx + dy * dy);

            // Clamp the stick to the rim of the base.
            if (mag > 1) {
                dx /= mag;
                dy /= mag;
            }

            stick = [dx, dy];

            var travel = radius - knob.offsetWidth / 2;
            knob.style.transform = 'translate(' + (dx * travel) + 'px, ' +
                (dy * travel) + 'px)';
        },
        releasePad = function () {
            padTouch = null;
            stick = [0, 0];
            pad.className = 'joystick';
            knob.style.transform = ''; // Springs back to center via CSS.
        },
        findTouch = function (e) {
            if (padTouch === null)
                return null;
            for (var i = 0; i < e.changedTouches.length; i++) {
                if (e.changedTouches[i].identifier == padTouch)
                    return e.changedTouches[i];
            }
            return null;
        };

    pad.addEventListener('touchstart', function (e) {
        e.preventDefault();
        game.sound.unlock();
        if (padTouch !== null)
            return;
        var t = e.changedTouches[0];
        padTouch = t.identifier;
        pad.className = 'joystick active';
        trackStick(t);
    });

    pad.addEventListener('touchmove', function (e) {
        e.preventDefault();
        var t = findTouch(e);
        if (t)
            trackStick(t);
    });

    pad.addEventListener('touchend', function (e) {
        e.preventDefault();
        if (findTouch(e))
            releasePad();
    });

    pad.addEventListener('touchcancel', function (e) {
        if (findTouch(e))
            releasePad();
    });

    fire.addEventListener('touchstart', function (e) {
        e.preventDefault();
        game.sound.unlock();
        fire.className = 'fire-button active';
        game.keyState.on(Asteroids.FIRE);
    });

    var fireOff = function (e) {
        if (e.cancelable)
            e.preventDefault();
        fire.className = 'fire-button';
        game.keyState.off(Asteroids.FIRE);
    };
    fire.addEventListener('touchend', fireOff);
    fire.addEventListener('touchcancel', fireOff);

    hyper.addEventListener('touchstart', function (e) {
        e.preventDefault();
        game.sound.unlock();
        hyper.className = 'hyper-button active';
        game.keyState.on(Asteroids.HYPER);
    });

    var hyperOff = function (e) {
        if (e.cancelable)
            e.preventDefault();
        hyper.className = 'hyper-button';
        game.keyState.off(Asteroids.HYPER);
    };
    hyper.addEventListener('touchend', hyperOff);
    hyper.addEventListener('touchcancel', hyperOff);

    return {
        // Called by the game loop each frame to apply the stick input.
        update: function () {
            if (game.player.isDead() || game.player.isHyper())
                return;

            var mag = Math.sqrt(stick[0] * stick[0] + stick[1] * stick[1]),
                velocity = game.player.getVelocity(),
                target = [0, 0]; // The velocity the stick asks for.

            if (mag >= DEADZONE) {
                var angle = Math.atan2(stick[1], stick[0]),
                    diff = angle - game.player.getDirection();

                // Shortest way around the circle, in [-PI, PI].
                diff = Math.atan2(Math.sin(diff), Math.cos(diff));

                // Turn toward the stick, faster the further it points away.
                game.player.rotate(Math.max(-ROTATE_SPEED,
                    Math.min(ROTATE_SPEED, diff / 2)));

                target[0] = MAX_SPEED * mag * Math.cos(angle);
                target[1] = MAX_SPEED * mag * Math.sin(angle);

                // Light the exhaust flame while pushing. (Adds no
                // velocity; the easing below does the real work.)
                if (mag > 0.3)
                    game.player.thrust(0);
            }

            // Ease the ship's velocity toward what the stick asks for:
            // its speed follows the stick's deflection, and it glides
            // to a stop when the stick is released.
            velocity[0] += (target[0] - velocity[0]) * SPEED_EASING;
            velocity[1] += (target[1] - velocity[1]) * SPEED_EASING;
        }
    };
}

Asteroids.asteroid = function (game, _gen) {
    // implements IScreenObject
    var position = [0, 0],
        velocity = [0, 0],
        direction = 0,
        generation = _gen,
        radius = 7,
        path = [
            [1, 7],
            [5, 5],
            [7, 1],
            [5, -3],
            [7, -7],
            [3, -9],
            [-1, -5],
            [-4, -2],
            [-8, -1],
            [-9, 3],
            [-5, 5],
            [-1, 3],
            [1, 7]
        ];

    return {
        getPosition: function () {
            return position;
        },
        setPosition: function (pos) {
            position = pos;
        },
        getVelocity: function () {
            return velocity;
        },
        setVelocity: function (vel) {
            velocity = vel;
            direction = Math.atan2(vel[1], vel[0]);
        },
        getSpeed: function () {
            return Math.sqrt(Math.pow(velocity[0], 2) + Math.pow(velocity[1], 2));
        },
        getRadius: function () {
            return radius * generation;
        },
        getWorldPath: function () {
            return Asteroids.worldPath(path, position, direction,
                generation);
        },
        getGeneration: function () {
            return generation;
        },
        move: function () {
            Asteroids.move(position, velocity);
        },
        draw: function (ctx) {
            Asteroids.drawPath(ctx, position, direction, generation, path);
            // ctx.setTransform(1, 0, 0, 1, position[0], position[1]);
            // ctx.beginPath();
            // ctx.arc(0, 0, radius*generation, 0, Math.PI*2, false);
            // ctx.stroke();
            // ctx.closePath();
        }
    }
}

/**
 * Collision geometry. Ships and rocks are tested against their actual
 * drawn outlines (not bounding circles), and bullets are swept along
 * the segment they traveled this frame so they can't skip through a
 * rock between frames.
 */

// A path's points in world coordinates, matching drawPath's transform.
Asteroids.worldPath = function (path, position, direction, scale) {
    var cos = Math.cos(direction) * scale,
        sin = Math.sin(direction) * scale,
        world = [];
    for (var i = 0; i < path.length; i++) {
        world.push([position[0] + path[i][0] * cos - path[i][1] * sin,
        position[1] + path[i][0] * sin + path[i][1] * cos]);
    }
    return world;
}

// Is a point inside a closed path? (Ray casting.)
Asteroids.pointInPath = function (pt, path) {
    var inside = false;
    for (var i = 0, j = path.length - 1; i < path.length; j = i++) {
        if ((path[i][1] > pt[1]) != (path[j][1] > pt[1]) &&
            pt[0] < (path[j][0] - path[i][0]) * (pt[1] - path[i][1]) /
            (path[j][1] - path[i][1]) + path[i][0])
            inside = !inside;
    }
    return inside;
}

// Do segments a-b and c-d cross?
Asteroids.segmentsIntersect = function (a, b, c, d) {
    var cross = function (p, q, r) {
        return (q[0] - p[0]) * (r[1] - p[1]) -
            (q[1] - p[1]) * (r[0] - p[0]);
    };
    return (cross(c, d, a) > 0) != (cross(c, d, b) > 0) &&
        (cross(a, b, c) > 0) != (cross(a, b, d) > 0);
}

// Does segment a-b pass within radius of center?
Asteroids.segmentHitsCircle = function (a, b, center, radius) {
    var dx = b[0] - a[0],
        dy = b[1] - a[1],
        len2 = dx * dx + dy * dy,
        t = len2 ? ((center[0] - a[0]) * dx +
            (center[1] - a[1]) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    var cx = a[0] + t * dx - center[0],
        cy = a[1] + t * dy - center[1];
    return cx * cx + cy * cy <= radius * radius;
}

// Does segment a-b cross into or end inside a closed path?
Asteroids.segmentHitsPath = function (a, b, path) {
    for (var i = 0; i < path.length - 1; i++) {
        if (Asteroids.segmentsIntersect(a, b, path[i], path[i + 1]))
            return true;
    }
    return Asteroids.pointInPath(b, path);
}

// Does a circle touch a closed path?
Asteroids.circleHitsPath = function (center, radius, path) {
    for (var i = 0; i < path.length - 1; i++) {
        if (Asteroids.segmentHitsCircle(path[i], path[i + 1],
            center, radius))
            return true;
    }
    return Asteroids.pointInPath(center, path);
}

// Do two closed paths overlap?
Asteroids.pathsCollide = function (p1, p2) {
    for (var i = 0; i < p1.length - 1; i++) {
        for (var j = 0; j < p2.length - 1; j++) {
            if (Asteroids.segmentsIntersect(p1[i], p1[i + 1],
                p2[j], p2[j + 1]))
                return true;
        }
    }
    return Asteroids.pointInPath(p1[0], p2) ||
        Asteroids.pointInPath(p2[0], p1);
}

/**
 * Creates an asteroid somewhere it won't immediately kill the player,
 * and adds it to the game.
 */
Asteroids.spawnAsteroid = function (game, gen, speed) {
    var a = Asteroids.asteroid(game, gen),
        player = game.player.getPosition(),
        pos = [0, 0],
        tries = 0;

    do {
        pos[0] = Math.random() * GAME_WIDTH;
        pos[1] = Math.random() * GAME_HEIGHT;
        tries++;
    } while (tries < 20 &&
        Math.sqrt(Math.pow(pos[0] - player[0], 2) +
            Math.pow(pos[1] - player[1], 2)) <
        SAFE_SPAWN_DISTANCE);

    a.setPosition(pos);
    a.setVelocity([Math.random() * speed - speed / 2,
    Math.random() * speed - speed / 2]);
    game.asteroids.push(a);
    return a;
}

Asteroids.level = function (game) {
    var level = 0;

    return {
        getLevel: function () {
            return level;
        },
        levelUp: function (game) {
            level++;
            game.log.debug('Congrats! On to level ' + level);

            game.player.resetAmmo();

            // More rocks each wave (up to a cap), and a bit faster.
            var speed = Math.min(ASTEROID_SPEED * (1 + (level - 1) / 10),
                ASTEROID_SPEED * 2),
                count = Math.min(level + ASTEROID_COUNT, MAX_ASTEROIDS);

            while (game.asteroids.generationCount(ASTEROID_GENERATIONS) <
                count) {
                Asteroids.spawnAsteroid(game, ASTEROID_GENERATIONS, speed);
            }
        },
    }
}

Asteroids.gameOver = function (game) {

    return function () {
        game.log.debug('Game over!');
        game.mode = 'over';

        var score = game.player.getScore(),
            canRestart = false;

        // Fire input restarts the game, after a beat so a last-second
        // shot doesn't skip past the high scores.
        var allowRestart = function () {
            setTimeout(function () { canRestart = true; }, 1000);
        };

        var restart = function (e) {
            if (!canRestart)
                return;
            if (e.type == 'keydown' && e.code != 'Space' && e.code != 'Enter')
                return;
            Asteroids.restart(game);
        };
        window.addEventListener('keydown', restart, true);
        window.addEventListener('touchstart', restart, true);
        window.addEventListener('click', restart, true);
        game.cleanups.push(function () {
            window.removeEventListener('keydown', restart, true);
            window.removeEventListener('touchstart', restart, true);
            window.removeEventListener('click', restart, true);
        });

        // A top-ten score gets the arcade initials treatment.
        if (game.highScores.qualifies(score)) {
            var form = document.createElement('form');
            form.className = 'initials';
            form.innerHTML =
                '<p>NEW HIGH SCORE: ' + score + '</p>' +
                '<p>ENTER YOUR INITIALS</p>' +
                '<input type="text" maxlength="3" autocomplete="off"/>' +
                '<button type="submit">OK</button>';
            game.home.appendChild(form);

            var input = form.querySelector('input');
            input.focus();

            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var name = input.value.replace(/[^a-z0-9]/gi, '')
                    .toUpperCase().slice(0, 3) || 'AAA';
                game.highScores.addScore(name, score);
                form.remove();
                allowRestart();
            });
        }
        else {
            allowRestart();
        }

        game.overlays.add({
            // implements IOverlay
            draw: function (ctx) {
                ctx.font = '30px System, monospace';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                ctx.fillText('GAME OVER', GAME_WIDTH / 2, GAME_HEIGHT / 2);

                var scores = game.highScores.getScores();
                ctx.font = '12px System, monospace';
                for (var i = 0; i < scores.length; i++) {
                    ctx.fillText(scores[i].name + '   ' + scores[i].score,
                        GAME_WIDTH / 2, GAME_HEIGHT / 2 + 20 + 14 * i);
                }

                if (canRestart) {
                    var hint = Asteroids.isMobile() ?
                        'TAP TO PLAY AGAIN' :
                        'PRESS SPACE TO PLAY AGAIN';
                    ctx.fillText(hint, GAME_WIDTH / 2,
                        GAME_HEIGHT / 2 + 34 + 14 * scores.length);
                }
            },
        });
    }
}

/**
 * Tears down a finished game and starts a fresh one in its place.
 */
Asteroids.restart = function (game) {
    clearInterval(game.pulse);
    for (var i = 0; i < game.cleanups.length; i++) {
        game.cleanups[i]();
    }
    return new Asteroids(game.home, 'playing');
}

Asteroids.highScores = function (game) {
    var scores = [];

    if (t = localStorage.getItem('high-scores')) {
        scores = JSON.parse(t);
    }

    return {
        getScores: function () {
            return scores;
        },
        qualifies: function (_score) {
            if (_score <= 0)
                return false;
            if (scores.length < 10)
                return true;
            return _score > scores[scores.length - 1].score;
        },
        addScore: function (_name, _score) {
            scores.push({ name: _name, score: _score });
            scores.sort(function (a, b) { return b.score - a.score; });
            if (scores.length > 10) {
                scores.length = 10;
            }
            game.log.debug('Saving high scores.');
            var str = JSON.stringify(scores);
            localStorage.setItem('high-scores', str);
        },
    }
}

/**
 * Sound effects, synthesized with the Web Audio API. A singleton,
 * shared across restarts; silent until unlock() runs after a user
 * gesture (a browser autoplay requirement).
 */
Asteroids.sound = function () {
    if (Asteroids._sound)
        return Asteroids._sound;

    var ctx = null, // The AudioContext; created by unlock().
        master = null,
        noise = null, // A reusable buffer of white noise.
        muted = true, // Starts muted; M toggles the sound on.
        saucerNodes = null,
        thrustNode = null;

    var unlock = function () {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!ctx && AC) {
            ctx = new AC();
            master = ctx.createGain();
            master.gain.value = muted ? 0 : 0.6;
            master.connect(ctx.destination);

            noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
            var data = noise.getChannelData(0);
            for (var i = 0; i < data.length; i++) {
                data[i] = Math.random() * 2 - 1;
            }
        }
        if (ctx && ctx.state == 'suspended')
            ctx.resume();
    };

    // A gain node with a percussive envelope, feeding the master.
    var envelope = function (peak, duration, when) {
        var t = ctx.currentTime + (when || 0),
            gain = ctx.createGain();
        gain.gain.setValueAtTime(peak, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + duration);
        gain.connect(master);
        return gain;
    };

    // A short tone sweeping between two frequencies.
    var blip = function (type, from, to, peak, duration, when) {
        var t = ctx.currentTime + (when || 0),
            osc = ctx.createOscillator();
        osc.type = type;
        osc.frequency.setValueAtTime(from, t);
        osc.frequency.exponentialRampToValueAtTime(to, t + duration);
        osc.connect(envelope(peak, duration, when));
        osc.start(t);
        osc.stop(t + duration);
    };

    // A burst of filtered noise.
    var boom = function (freq, peak, duration) {
        var src = ctx.createBufferSource(),
            filter = ctx.createBiquadFilter();
        src.buffer = noise;
        filter.type = 'lowpass';
        filter.frequency.value = freq;
        src.connect(filter);
        filter.connect(envelope(peak, duration));
        src.start();
        src.stop(ctx.currentTime + duration);
    };

    Asteroids._sound = {
        unlock: unlock,
        toggleMute: function () {
            muted = !muted;
            if (master)
                master.gain.value = muted ? 0 : 0.6;
            return muted;
        },
        fire: function () {
            if (!ctx) return;
            blip('square', 880, 220, 0.12, 0.18);
        },
        explosion: function (size) {
            if (!ctx) return;
            // Bigger things explode deeper and longer.
            boom(1800 / size, 0.5, 0.2 + size * 0.12);
        },
        beat: function (low) {
            if (!ctx) return;
            blip('triangle', low ? 100 : 130, low ? 55 : 70, 0.35, 0.12);
        },
        hyperspace: function () {
            if (!ctx) return;
            blip('sawtooth', 800, 60, 0.15, 0.35);
        },
        extraLife: function () {
            if (!ctx) return;
            for (var i = 0; i < 3; i++) {
                blip('square', 700, 1000, 0.12, 0.09, i * 0.12);
            }
        },
        thrust: function (active) {
            if (!ctx) return;
            if (active && !thrustNode) {
                var src = ctx.createBufferSource(),
                    filter = ctx.createBiquadFilter(),
                    gain = ctx.createGain();
                src.buffer = noise;
                src.loop = true;
                filter.type = 'lowpass';
                filter.frequency.value = 350;
                gain.gain.value = 0.18;
                src.connect(filter);
                filter.connect(gain);
                gain.connect(master);
                src.start();
                thrustNode = src;
            }
            else if (!active && thrustNode) {
                thrustNode.stop();
                thrustNode = null;
            }
        },
        saucer: function (active, small) {
            if (!ctx) return;
            if (active && !saucerNodes) {
                // A warbling siren: an LFO wobbling a tone's pitch.
                var osc = ctx.createOscillator(),
                    lfo = ctx.createOscillator(),
                    depth = ctx.createGain(),
                    gain = ctx.createGain();
                osc.type = 'square';
                osc.frequency.value = small ? 620 : 280;
                lfo.frequency.value = small ? 6 : 4;
                depth.gain.value = small ? 150 : 70;
                lfo.connect(depth);
                depth.connect(osc.frequency);
                gain.gain.value = 0.07;
                osc.connect(gain);
                gain.connect(master);
                osc.start();
                lfo.start();
                saucerNodes = [osc, lfo];
            }
            else if (!active && saucerNodes) {
                saucerNodes[0].stop();
                saucerNodes[1].stop();
                saucerNodes = null;
            }
        },
    };
    return Asteroids._sound;
}

/**
 * Draws the attract-mode (title) screen.
 */
Asteroids.drawAttract = function (ctx, game, now) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.font = '48px System, monospace';
    ctx.fillText('ASTEROIDS', GAME_WIDTH / 2, GAME_HEIGHT / 3);

    // Blink the start prompt.
    if (Math.floor(now / 600) % 2) {
        ctx.font = '16px System, monospace';
        ctx.fillText(Asteroids.isMobile() ?
            'TAP FIRE TO START' : 'PRESS SPACE TO START',
            GAME_WIDTH / 2, GAME_HEIGHT / 2);
    }

    var scores = game.highScores.getScores();
    if (scores.length) {
        ctx.font = '12px System, monospace';
        ctx.fillText('HIGH SCORES', GAME_WIDTH / 2, GAME_HEIGHT / 2 + 50);
        for (var i = 0; i < Math.min(scores.length, 5); i++) {
            ctx.fillText(scores[i].name + '   ' + scores[i].score,
                GAME_WIDTH / 2, GAME_HEIGHT / 2 + 70 + 14 * i);
        }
    }
}

Asteroids.drawPath = function (ctx, position, direction, scale, path, color) {
    if (!color) {
        color = '#fff';
    }
    ctx.strokeStyle = color;
    ctx.setTransform(Math.cos(direction) * scale, Math.sin(direction) * scale,
        -Math.sin(direction) * scale, Math.cos(direction) * scale,
        position[0], position[1]);

    ctx.beginPath();
    ctx.moveTo(path[0][0], path[0][1]);
    for (var i = 1; i < path.length; i++) {
        ctx.lineTo(path[i][0], path[i][1]);
    }
    ctx.stroke();
    ctx.closePath();
    ctx.strokeStyle = '#fff';
}

Asteroids.move = function (position, velocity) {
    position[0] += velocity[0];
    if (position[0] < 0)
        position[0] = GAME_WIDTH + position[0];
    else if (position[0] > GAME_WIDTH)
        position[0] -= GAME_WIDTH;

    position[1] += velocity[1];
    if (position[1] < 0)
        position[1] = GAME_HEIGHT + position[1];
    else if (position[1] > GAME_HEIGHT)
        position[1] -= GAME_HEIGHT;
}

Asteroids.stars = function (game) {
    var stars = [];

    var generate = function () {
        // About as dense as 50 stars on the original 640x480 field.
        var count = Math.round(GAME_WIDTH * GAME_HEIGHT / 6000);
        stars = [];
        for (var i = 0; i < count; i++) {
            stars.push([Math.random() * GAME_WIDTH, Math.random() * GAME_HEIGHT]);
        }
    };
    generate();
    window.addEventListener('resize', generate);
    game.cleanups.push(function () {
        window.removeEventListener('resize', generate);
    });

    return {
        draw: function (ctx) {
            var ii = stars.length;
            for (var i = 0; i < ii; i++) {
                ctx.fillRect(stars[i][0], stars[i][1], 1, 1);
            }
        }
    }
}

Asteroids.play = function (game) {
    var ctx = game.playfield.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.strokeStyle = 'white';

    var speed = ASTEROID_SPEED;

    game.paused = false;
    game.mode = 'attract';

    var bullets = [],
        saucer = null,
        saucerBullets = [],
        nextSaucer = 0,
        last_fire_state = false,
        last_hyper_state = false,
        last_asteroid_count = 0,
        next_beat = 0,
        beat_low = true,
        extra_lives = 0;

    var startGame = function () {
        game.sound.unlock();
        game.mode = 'playing';
        game.asteroids.splice(0, game.asteroids.length);
        game.level.levelUp(game);
        nextSaucer = Date.now() + SAUCER_TIME * (1 + Math.random());
        last_fire_state = true; // Don't fire off the starting keypress.
    };

    // Add a star field.
    game.overlays.add(Asteroids.stars(game));

    if (game.startMode == 'playing') {
        startGame();
    }
    else {
        // Some rocks drifting behind the attract screen.
        for (var i = 0; i < 5; i++) {
            Asteroids.spawnAsteroid(game, ASTEROID_GENERATIONS, speed);
        }
    }

    game.pulse = setInterval(function () {
        if (game.paused)
            return;

        var now = Date.now(),
            kill_asteroids = [],
            new_asteroids = [],
            kill_bullets = [];

        ctx.save();
        ctx.clearRect(0, 0, GAME_WIDTH, GAME_HEIGHT);

        var fire_state = game.keyState.getState(Asteroids.FIRE);

        // On the attract screen, the fire control starts the game.
        if (game.mode == 'attract') {
            if (fire_state && !last_fire_state)
                startGame();
            else
                last_fire_state = fire_state;
        }

        if (game.mode == 'playing') {
            // Be nice and award extra lives first.
            var t_extra_lives = game.player.getScore() / POINTS_TO_EXTRA_LIFE;
            t_extra_lives = Math.floor(t_extra_lives);
            if (t_extra_lives > extra_lives) {
                game.player.extraLife(game);
                game.sound.extraLife();
            }
            extra_lives = t_extra_lives;

            if (game.keyState.getState(Asteroids.UP)) {
                game.player.thrust(THRUST_ACCEL);
            }

            if (game.keyState.getState(Asteroids.DOWN)) {
                game.player.brake(BRAKE_POWER);
            }

            if (game.keyState.getState(Asteroids.LEFT)) {
                game.player.rotate(-ROTATE_SPEED);
            }

            if (game.keyState.getState(Asteroids.RIGHT)) {
                game.player.rotate(ROTATE_SPEED);
            }

            // Apply the touch joystick, if there is one.
            if (game.controls && game.controls.update) {
                game.controls.update();
            }

            if (HYPERSPACE_ENABLED) {
                var hyper_state = game.keyState.getState(Asteroids.HYPER);
                if (hyper_state && !last_hyper_state) {
                    game.player.hyperspace(game);
                }
                last_hyper_state = hyper_state;
            }

            if (fire_state &&
                (fire_state != last_fire_state) &&
                (bullets.length < MAX_BULLETS)) {
                var b = game.player.fire(game);
                if (b) {
                    bullets.push(b);
                    game.sound.fire();
                }
            }
            last_fire_state = fire_state;
        }

        var playerActive = game.mode != 'attract' &&
            !game.player.isDead() &&
            !game.player.isHyper();

        if (playerActive) {
            game.player.move();
            game.player.draw(ctx);
        }
        game.sound.thrust(playerActive && game.player.isThrusting());

        // The ship's outline in world coordinates, for collision
        // tests. Null while the ship can't be hit.
        var playerPath = playerActive && !game.player.isInvincible() ?
            game.player.getWorldPath() : null;

        for (var k = 0; k < bullets.length; k++) {
            if (!bullets[k])
                continue;

            if (bullets[k].getAge() > MAX_BULLET_AGE) {
                kill_bullets.push(k);
                continue;
            }
            bullets[k].birthday();
            bullets[k].move();
            bullets[k].draw(ctx);

            // Friendly fire: your own shot can wrap around (or be
            // chased down) and hit you.
            if (playerPath && bullets[k].getAge() > FRIENDLY_FIRE_AGE &&
                Asteroids.segmentHitsPath(bullets[k].getLastPosition(),
                    bullets[k].getPosition(), playerPath)) {
                game.log.debug('You shot yourself!');
                kill_bullets.push(k);
                game.player.die(game);
                playerPath = null;
            }
        }

        for (var r = kill_bullets.length - 1; r >= 0; r--) {
            bullets.splice(kill_bullets[r], 1);
        }

        // Time for a saucer visit?
        if (game.mode == 'playing' && !saucer && now > nextSaucer) {
            // Small saucers get more likely as the score climbs.
            var small = Math.random() <
                Math.min(0.9, 0.2 + game.level.getLevel() * 0.05 +
                    game.player.getScore() / 40000);
            saucer = Asteroids.saucer(game, small);
            game.log.debug('A ' + (small ? 'small' : 'big') +
                ' saucer appears!');
        }

        var scheduleSaucer = function () {
            saucer = null;
            nextSaucer = now + SAUCER_TIME * (0.5 + Math.random());
        };

        if (saucer) {
            var shot = saucer.update(now);
            if (shot) {
                saucerBullets.push(shot);
                game.sound.fire();
            }
            saucer.draw(ctx);

            if (saucer.isGone())
                scheduleSaucer();
        }
        game.sound.saucer(!!saucer, !!saucer && saucer.isSmall());

        // Shot the saucer?
        if (saucer) {
            for (var j = 0; j < bullets.length; j++) {
                if (bullets[j] && Asteroids.segmentHitsCircle(
                    bullets[j].getLastPosition(), bullets[j].getPosition(),
                    saucer.getPosition(), saucer.getRadius())) {
                    game.log.debug('You shot the saucer!');
                    game.player.addScore(saucer.getScore());
                    game.sound.explosion(3);
                    bullets.splice(j, 1);
                    scheduleSaucer();
                    break;
                }
            }
        }

        // Flew into the saucer?
        if (saucer && playerPath &&
            Asteroids.circleHitsPath(saucer.getPosition(),
                saucer.getRadius(), playerPath)) {
            game.player.addScore(saucer.getScore());
            game.sound.explosion(3);
            scheduleSaucer();
            game.player.die(game);
            playerPath = null;
        }

        // The saucer's bullets fly, age, and menace the player.
        var kill_saucer_bullets = [];
        for (var k = 0; k < saucerBullets.length; k++) {
            if (saucerBullets[k].getAge() > SAUCER_BULLET_AGE) {
                kill_saucer_bullets.push(k);
                continue;
            }
            saucerBullets[k].birthday();
            saucerBullets[k].move();
            saucerBullets[k].draw(ctx);

            if (playerPath &&
                Asteroids.segmentHitsPath(
                    saucerBullets[k].getLastPosition(),
                    saucerBullets[k].getPosition(), playerPath)) {
                kill_saucer_bullets.push(k);
                game.player.die(game);
                playerPath = null;
            }
            // Friendly fire: a shot that wraps around can down its
            // own saucer.
            else if (saucer &&
                saucerBullets[k].getAge() > FRIENDLY_FIRE_AGE &&
                Asteroids.segmentHitsCircle(
                    saucerBullets[k].getLastPosition(),
                    saucerBullets[k].getPosition(),
                    saucer.getPosition(), saucer.getRadius())) {
                game.log.debug('The saucer shot itself!');
                kill_saucer_bullets.push(k);
                game.sound.explosion(3);
                scheduleSaucer();
            }
        }
        for (var r = kill_saucer_bullets.length - 1; r >= 0; r--) {
            saucerBullets.splice(kill_saucer_bullets[r], 1);
        }

        var asteroids = game.asteroids.getIterator();
        for (var i = 0; i < game.asteroids.length; i++) {
            var killit = false,
                scoreit = false;
            asteroids[i].move();
            asteroids[i].draw(ctx);

            var rockPath = asteroids[i].getWorldPath();

            // Destroy the asteroid
            for (var j = 0; j < bullets.length; j++) {
                if (!bullets[j])
                    continue;
                if (Asteroids.segmentHitsPath(bullets[j].getLastPosition(),
                    bullets[j].getPosition(), rockPath)) {
                    game.log.debug('You shot an asteroid!');
                    // Destroy the bullet.
                    bullets.splice(j, 1);
                    killit = true;
                    scoreit = true;
                    break;
                }
            }

            // Saucer fire breaks rocks too, but pays nothing.
            if (!killit) {
                for (var j = 0; j < saucerBullets.length; j++) {
                    if (Asteroids.segmentHitsPath(
                        saucerBullets[j].getLastPosition(),
                        saucerBullets[j].getPosition(), rockPath)) {
                        saucerBullets.splice(j, 1);
                        killit = true;
                        break;
                    }
                }
            }

            // So does the saucer itself, the hard way.
            if (!killit && saucer &&
                Asteroids.circleHitsPath(saucer.getPosition(),
                    saucer.getRadius(), rockPath)) {
                game.sound.explosion(3);
                scheduleSaucer();
                killit = true;
            }

            // Kill the asteroid?
            if (killit) {
                var _gen = asteroids[i].getGeneration() - 1;
                if (_gen > 0) {
                    // Create children ;) a bit faster than their parent.
                    var kid_speed = speed *
                        Math.pow(1.3, ASTEROID_GENERATIONS - _gen);
                    for (var n = 0; n < ASTEROID_CHILDREN; n++) {
                        var a = Asteroids.asteroid(game, _gen);
                        var _pos = [asteroids[i].getPosition()[0],
                        asteroids[i].getPosition()[1]];
                        a.setPosition(_pos);
                        a.setVelocity([Math.random() * kid_speed - kid_speed / 2,
                        Math.random() * kid_speed - kid_speed / 2]);
                        new_asteroids.push(a);
                    }
                }
                if (scoreit) {
                    // Smaller rocks are worth more.
                    game.player.addScore(
                        ASTEROID_SCORES[asteroids[i].getGeneration()] || 10);
                }
                game.sound.explosion(asteroids[i].getGeneration() + 1);
                kill_asteroids.push(i);
                continue;
            }

            // Kill the player?
            if (playerPath &&
                Asteroids.pathsCollide(playerPath, rockPath)) {
                game.player.die(game);
                playerPath = null;
            }
        }

        kill_asteroids.sort(function (a, b) { return a - b; });
        for (var m = kill_asteroids.length - 1; m >= 0; m--) {
            game.asteroids.splice(kill_asteroids[m], 1);
        }

        for (var o = 0; o < new_asteroids.length; o++) {
            game.asteroids.push(new_asteroids[o]);
        }

        ctx.restore();

        // Do we need to level up?
        if (0 == game.asteroids.length &&
            last_asteroid_count != 0) {
            setTimeout(function () {
                if (game.mode == 'playing') {
                    game.level.levelUp(game);
                }
            }, LEVEL_TIMEOUT);
        }

        last_asteroid_count = game.asteroids.length;

        // The heartbeat thump, quickening as the field thins out.
        if (game.mode == 'playing' && !game.player.isDead() &&
            now > next_beat) {
            game.sound.beat(beat_low);
            beat_low = !beat_low;
            next_beat = now + 250 + 100 * Math.min(game.asteroids.length, 8);
        }

        // Draw overlays.
        game.overlays.draw(ctx);

        if (game.mode == 'attract') {
            Asteroids.drawAttract(ctx, game, now);
        }

        // Update the info pane.
        game.info.setLives(game, game.player.getLives());
        game.info.setScore(game, game.player.getScore());
        game.info.setAmmo(game, game.player.getAmmo());
        game.info.setLevel(game, game.level.getLevel());
    }, FRAME_PERIOD);
}

// Some boring constants.
Asteroids.LOG_ALL = 0;
Asteroids.LOG_INFO = 1;
Asteroids.LOG_DEBUG = 2;
Asteroids.LOG_WARNING = 3;
Asteroids.LOG_ERROR = 4;
Asteroids.LOG_CRITICAL = 5;
Asteroids.LOG_NONE = 6;

Asteroids.LEFT = 37;
Asteroids.UP = 38;
Asteroids.RIGHT = 39;
Asteroids.DOWN = 40;
Asteroids.FIRE = 32;
Asteroids.HYPER = 16;

// Load it up!
new Asteroids(document.getElementById('asteroids'));
