(function ($) {

    const wdtSectionsOptionsHandler = function($scope) {
        const animationEffectInstance = new wdtWidgetsAnimationEffectHandlerInit($scope);
        animationEffectInstance.init();
    };

    const wdtWidgetsAnimationEffectHandlerInit = function($scope) {

        const $self   = this,
            $window   = $(window),
            $sectionId = $scope.data('id'),
            $editMode = Boolean(elementorFrontend.isEditMode()),
            $activeBreakpoints = elementorFrontend.config.responsive.activeBreakpoints,
            $deviceMode = elementorFrontend.getCurrentDeviceMode();

        let $activeBreakpointkeys = [];
        let $animationEffectSettings = false;
        let $mouseMoveItemSettings = {};
        let $scrollItemSettings = {};
        let scrollItems = []; // stores scroll wrappers for the rAF loop
        let scrollRaf = null;
        let scrollTick = false;
        let resizeRaf = null;

        let mouseMoveState = {
            raf: null,
            running: false,
            boundEl: null
        };

        $self.init = function() {
            $self.animationEffectInit();
        };

        $self.filterObjects = function($settings, $searchKey) {
            if(!$settings) return false;
            let $settingKeys = Object.keys($settings).filter((key) => key.includes($searchKey));
            let $filteredSettings = $settingKeys.reduce((cur, key) => { return Object.assign(cur, { [key]: $settings[key] })}, {});
            if(Object.keys($filteredSettings).length) {
                return $filteredSettings;
            }
            return false;
        };

        $self.animationEffectInit = function() {

            if($editMode) {
                $animationEffectSettings = $self.generateEditorSettings($sectionId);
            } else {
                $animationEffectSettings = $scope.data('settings') || false;
                $animationEffectSettings = $self.filterObjects($animationEffectSettings, 'wdt_');
            }

            if(!$animationEffectSettings || !$animationEffectSettings['wdt_animation_effect'] || $animationEffectSettings['wdt_animation_effect'] === 'none' || $animationEffectSettings['wdt_animation_effect'] === '') {
                return false;
            }

            // Update breakpoints
            $self.updateActiveBreakpoints();

            // Generate Background sections for effects
            $self.generateBgItemsInSections();

            // Mouse Move Effect
            if(Object.keys($mouseMoveItemSettings).length) {
                $self.animationEffectMouseMove();
            }

            // Scroll Effect
            if(Object.keys($scrollItemSettings).length) {
                $self.animationEffectScroll();
            }

            // Start scroll loop if needed
            if(scrollItems.length) {
                $self.startScrollLoop();
                // recalc on resize
                $window.on('resize.wdtBgeffects', function() {
                    if(resizeRaf) cancelAnimationFrame(resizeRaf);
                    resizeRaf = requestAnimationFrame(function() {
                        $self.recalculateScrollItems();
                    });
                });
            }

            // cleanup on destroy (Elementor)
            $scope.on('destroy', function() {
                $self.destroyAll();
            });

        };

        $self.generateEditorSettings = function($sectionId) {

            let $editorModels     = null,
            $editorSettings       = {};

            if(!window.elementor.hasOwnProperty('elements')) {
                return false;
            }

            $editorModels = window.elementor.elements.models;
            if(!$editorModels) {
                return false;
            }

            $.each( $editorModels, function( index, obj ) {
                if($sectionId === obj.id) {
                    $editorSettings = obj.attributes.settings.attributes;
                }
            });

            if(!Object.keys($editorSettings).length) {
                return false;
            }

            return $self.filterObjects($editorSettings, 'wdt_');

        };

        $self.updateActiveBreakpoints = function() {

            $.each($activeBreakpoints, function (key, value) {
                if('widescreen' === key) {
                    $activeBreakpointkeys.push( 'desktop' );
                    $activeBreakpointkeys.push( key );
                } else {
                    $activeBreakpointkeys.push( key );
                }

            });

            if ( -1 === $activeBreakpointkeys.indexOf( 'widescreen' ) ) {
                $activeBreakpointkeys.push( 'desktop' );
            }

        };

        $self.generateBreakpointwiseBgItems = function($section) {

            let $bgItems = {};
            let $wdt_bg_image = ($section['wdt_bg_image'] && '' != $section['wdt_bg_image']['url']) ? $section['wdt_bg_image']['url'] : '';
            let $wdt_bg_position = ($section['wdt_bg_position'] && '' != $section['wdt_bg_position']) ? $section['wdt_bg_position'] : 'center center';
            let $wdt_bg_size = ($section['wdt_bg_size'] && '' != $section['wdt_bg_size']) ? $section['wdt_bg_size'] : 'cover';
            let $wdt_bg_repeat = ($section['wdt_bg_repeat'] && '' != $section['wdt_bg_repeat']) ? $section['wdt_bg_repeat'] : 'no-repeat';

            $activeBreakpointkeys.forEach( function( breakpoint ) {

                if('desktop' === breakpoint) {
                    $bgItems[breakpoint] = {
                        'bgImage' : $wdt_bg_image,
                        'bgPosition' : $wdt_bg_position,
                        'bgSize' : $wdt_bg_size,
                        'bgRepeat' : $wdt_bg_repeat
                    };
                } else {
                    $bgItems[breakpoint] = {
                        'bgImage' : ($section['wdt_bg_image_' + breakpoint] && '' != $section['wdt_bg_image_' + breakpoint]['url']) ? $section['wdt_bg_image_' + breakpoint]['url'] : $wdt_bg_image,
                        'bgPosition' : ($section['wdt_bg_position_' + breakpoint] && '' != $section['wdt_bg_position_' + breakpoint]) ? $section['wdt_bg_position_' + breakpoint] : $wdt_bg_position,
                        'bgSize' : ($section['wdt_bg_size_' + breakpoint] && '' != $section['wdt_bg_size_' + breakpoint]) ? $section['wdt_bg_size_' + breakpoint] : $wdt_bg_size,
                        'bgRepeat' : ($section['wdt_bg_repeat_' + breakpoint] && '' != $section['wdt_bg_repeat_' + breakpoint]) ? $section['wdt_bg_repeat_' + breakpoint] : $wdt_bg_repeat
                    };
                }

            });

            return $bgItems;

        };

        $self.generateBgItemsInSections = function() {

            // Remove existing background items
            $scope.find('.wdt-section-bgeffects-item').remove();

            // Generate background settings and layout html
            const $effectType = $animationEffectSettings['wdt_animation_effect'];

            let $bgItem = $self.generateBreakpointwiseBgItems($animationEffectSettings);

            if($effectType === 'none' || $effectType === '' || !$bgItem[$deviceMode]) {
                return false;
            }

            if(!$scope.hasClass('wdt-section-bgeffects')) {
                $scope.addClass('wdt-section-bgeffects');
            }

            const $bgImage = $bgItem[$deviceMode].bgImage;
            const $bgPosition = $bgItem[$deviceMode].bgPosition;
            const $bgSize = $bgItem[$deviceMode].bgSize;
            const $bgRepeat = $bgItem[$deviceMode].bgRepeat;

            if($effectType === 'mouse-move') {

                let $layout = $( '<div class="wdt-section-bgeffects-item wdt-effect-mouse-move-wrapper layer"><div class="wdt-section-bgeffects-image"></div></div>' ).prependTo($scope);

                let $bgCSS = {
                    'background-image': 'url(' + $bgImage + ')',
                    'background-position': $bgPosition,
                    'background-size': $bgSize,
                    'background-repeat': $bgRepeat,
                    'position': 'absolute',
                    'left': 0,
                    'top': 0,
                    'width': '100%',
                    'height': '100%',
                    'pointer-events': 'none'
                };

                $layout.find('.wdt-section-bgeffects-image').css($bgCSS);

                // Filter mouse move animation settings
                $mouseMoveItemSettings = $self.filterObjects($animationEffectSettings, 'wdt_mme_');
                $mouseMoveItemSettings['wdt_item'] = $layout;

            } else if($effectType === 'scroll') {

                let $layout = $( '<div class="wdt-section-bgeffects-item wdt-effect-scroll-wrapper"><div class="wdt-section-bgeffects-image"></div></div>' ).prependTo($scope);

                let $bgCSS = {
                    'background-image': 'url(' + $bgImage + ')',
                    'background-position': $bgPosition,
                    'background-size': $bgSize,
                    'background-repeat': $bgRepeat,
                    'position': 'absolute',
                    'left': 0,
                    'top': 0,
                    'width': '110%', // slightly larger for parallax breathing
                    'height': '110%',
                    'pointer-events': 'none'
                };

                $layout.find('.wdt-section-bgeffects-image').css($bgCSS);

                // Filter scroll animation settings
                $scrollItemSettings = $self.filterObjects($animationEffectSettings, 'wdt_sle_');
                $scrollItemSettings['wdt_item'] = $layout;

            }

        };

        $self.getMouseMoveResponsiveSettings = function($mouseMoveItem) {

            let $mouseMoveBreakpointItem = {};

            $activeBreakpointkeys.forEach( function( $breakpoint ) {

                if('desktop' === $breakpoint) {
                    $mouseMoveBreakpointItem[$breakpoint] = {
                        'speed' : ($mouseMoveItem['wdt_mme_speed'] && $mouseMoveItem['wdt_mme_speed']['size'] && '' != $mouseMoveItem['wdt_mme_speed']['size']) ? $mouseMoveItem['wdt_mme_speed']['size'] : 0.1,
                        'depth' : ($mouseMoveItem['wdt_mme_depth'] && $mouseMoveItem['wdt_mme_depth']['size'] && '' != $mouseMoveItem['wdt_mme_depth']['size']) ? $mouseMoveItem['wdt_mme_depth']['size'] : 1
                    };
                } else {
                    $mouseMoveBreakpointItem[$breakpoint] = {
                        'speed' : ($mouseMoveItem['wdt_mme_speed_' + $breakpoint] && $mouseMoveItem['wdt_mme_speed_' + $breakpoint]['size'] && '' != $mouseMoveItem['wdt_mme_speed_' + $breakpoint]['size']) ? $mouseMoveItem['wdt_mme_speed_' + $breakpoint]['size'] : ($mouseMoveItem['wdt_mme_speed'] && $mouseMoveItem['wdt_mme_speed']['size'] ? $mouseMoveItem['wdt_mme_speed']['size'] : 0.1),
                        'depth' : ($mouseMoveItem['wdt_mme_depth_' + $breakpoint] && $mouseMoveItem['wdt_mme_depth_' + $breakpoint]['size'] && '' != $mouseMoveItem['wdt_mme_depth_' + $breakpoint]['size']) ? $mouseMoveItem['wdt_mme_depth_' + $breakpoint]['size'] : ($mouseMoveItem['wdt_mme_depth'] && $mouseMoveItem['wdt_mme_depth']['size'] ? $mouseMoveItem['wdt_mme_depth']['size'] : 1)
                    };
                }

            });

            return $mouseMoveBreakpointItem;

        };

        $self.animationEffectMouseMove = function() {

            // Responsivewise Options
            let $mouseMoveBreakpointwiseItem = $self.getMouseMoveResponsiveSettings($mouseMoveItemSettings);

            // Get settings
            if(!$mouseMoveBreakpointwiseItem[$deviceMode]) {
                return false;
            }

            const $speed = parseFloat($mouseMoveBreakpointwiseItem[$deviceMode].speed) || 0.1;
            const $depth = parseFloat($mouseMoveBreakpointwiseItem[$deviceMode].depth) || 1;
            const $moveAlong = $mouseMoveItemSettings['wdt_mme_move_along'] ? $mouseMoveItemSettings['wdt_mme_move_along'] : 'both';
            const $invertMovement = $mouseMoveItemSettings['wdt_mme_invert_movement'] ? Boolean($mouseMoveItemSettings['wdt_mme_invert_movement']) : false;

            // Apply mouse move effect to the specific wrapper image
            let $wrapper = $mouseMoveItemSettings['wdt_item'].find('.wdt-section-bgeffects-image');
            $wrapper.attr('data-depth', $depth);

            // compute scalars
            let scalarX = 10.0, scalarY = 10.0;
            if($moveAlong === 'x-axis') { scalarY = 0.0; }
            if($moveAlong === 'y-axis') { scalarX = 0.0; }

            scalarX *= $depth;
            scalarY *= $depth;
            if($invertMovement) { scalarX = -scalarX; scalarY = -scalarY; }

            // Touch devices: skip unless in editor
            const isTouch = ('ontouchstart' in window) || navigator.maxTouchPoints > 0;
            if(isTouch && !$editMode) {
                return false;
            }

            // Bound element is the section container ($scope)
            const $bound = $scope;

            // smoothing state
            let targetX = 0, targetY = 0;
            let currentX = 0, currentY = 0;

            function lerp(a, b, t) { return a + (b - a) * t; }

            // onPointerMove
            function onPointerMove(e) {
                const rect = $bound[0].getBoundingClientRect();
                let clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] && e.touches[0].clientX) || 0;
                let clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] && e.touches[0].clientY) || 0;

                const relX = ((clientX - rect.left) / (rect.width || 1)) * 2 - 1; // -1 .. 1
                const relY = ((clientY - rect.top) / (rect.height || 1)) * 2 - 1; // -1 .. 1

                targetX = relX * scalarX;
                targetY = relY * scalarY;

                // ensure loop running
                if(!mouseMoveState.running) {
                    mouseMoveState.running = true;
                    mouseMoveLoop();
                }
            }

            function mouseMoveLoop() {
                // speed acts as lerp factor (0..1)
                const t = Math.min(Math.max($speed, 0.01), 0.95);
                currentX = lerp(currentX, targetX, t);
                currentY = lerp(currentY, targetY, t);

                $wrapper.css('transform', 'translate3d(' + currentX.toFixed(2) + 'px,' + currentY.toFixed(2) + 'px,0)');

                mouseMoveState.raf = requestAnimationFrame(mouseMoveLoop);
            }

            // Start listeners
            $bound.on('mousemove.wdt_mme touchmove.wdt_mme', onPointerMove);

            // Reset on leave
            $bound.on('mouseleave.wdt_mme touchend.wdt_mme touchcancel.wdt_mme', function() {
                targetX = 0; targetY = 0;
                // allow to settle then stop
                setTimeout(function() {
                    if(Math.abs(currentX) < 0.5 && Math.abs(currentY) < 0.5) {
                        if(mouseMoveState.raf) cancelAnimationFrame(mouseMoveState.raf);
                        mouseMoveState.raf = null;
                        mouseMoveState.running = false;
                        $wrapper.css('transform', '');
                        currentX = currentY = 0;
                    }
                }, 250);
            });

            // Clean up on destroy
            $scope.on('destroy', function() {
                $bound.off('.wdt_mme');
                if(mouseMoveState.raf) cancelAnimationFrame(mouseMoveState.raf);
                mouseMoveState.raf = null;
                mouseMoveState.running = false;
            });

            // If editor preview, start with a slight movement so editor shows effect
            if($editMode) {
                // fake a small target to show movement
                targetX = scalarX * 0.05;
                targetY = scalarY * 0.05;
                if(!mouseMoveState.running) { mouseMoveState.running = true; mouseMoveLoop(); }
            }

        };

        $self.getScrollResponsiveSettings = function($scrollItem) {

            let $scrollBreakpointItem = {};

            let $wdt_sle_parallax_x_depth = ($scrollItem['wdt_sle_parallax_x_depth'] && '' != $scrollItem['wdt_sle_parallax_x_depth']['size']) ? $scrollItem['wdt_sle_parallax_x_depth']['size'] : 50;
            let $wdt_sle_parallax_y_depth = ($scrollItem['wdt_sle_parallax_y_depth'] && '' != $scrollItem['wdt_sle_parallax_y_depth']['size']) ? $scrollItem['wdt_sle_parallax_y_depth']['size'] : 50;
            let $wdt_sle_rotate_x_angle = ($scrollItem['wdt_sle_rotate_x_angle'] && '' != $scrollItem['wdt_sle_rotate_x_angle']['size']) ? $scrollItem['wdt_sle_rotate_x_angle']['size'] : 45;
            let $wdt_sle_rotate_y_angle = ($scrollItem['wdt_sle_rotate_y_angle'] && '' != $scrollItem['wdt_sle_rotate_y_angle']['size']) ? $scrollItem['wdt_sle_rotate_y_angle']['size'] : 45;
            let $wdt_sle_rotate_z_angle = ($scrollItem['wdt_sle_rotate_z_angle'] && '' != $scrollItem['wdt_sle_rotate_z_angle']['size']) ? $scrollItem['wdt_sle_rotate_z_angle']['size'] : 45;
            let $wdt_sle_scale_value = ($scrollItem['wdt_sle_scale_value'] && '' != $scrollItem['wdt_sle_scale_value']['size']) ? $scrollItem['wdt_sle_scale_value']['size'] : 1;
            let $wdt_sle_blur_value = ($scrollItem['wdt_sle_blur_value'] && '' != $scrollItem['wdt_sle_blur_value']['size']) ? $scrollItem['wdt_sle_blur_value']['size'] : 0;
            let $wdt_sle_opacity_value = ($scrollItem['wdt_sle_opacity_value'] && '' != $scrollItem['wdt_sle_opacity_value']['size']) ? $scrollItem['wdt_sle_opacity_value']['size'] : 1;

            $activeBreakpointkeys.forEach( function( $breakpoint ) {

                if('desktop' === $breakpoint) {
                    $scrollBreakpointItem[$breakpoint] = {
                        'parallaxDepthX': $wdt_sle_parallax_x_depth,
                        'parallaxDepthY': $wdt_sle_parallax_y_depth,
                        'rotateAngleX'  : $wdt_sle_rotate_x_angle,
                        'rotateAngleY'  : $wdt_sle_rotate_y_angle,
                        'rotateAngleZ'  : $wdt_sle_rotate_z_angle,
                        'scaleValue'    : $wdt_sle_scale_value,
                        'blurValue'     : $wdt_sle_blur_value,
                        'opacityValue'  : $wdt_sle_opacity_value
                    };
                } else {
                    $scrollBreakpointItem[$breakpoint] = {
                        'parallaxDepthX' : ($scrollItem['wdt_sle_parallax_x_depth_' + $breakpoint] && '' != $scrollItem['wdt_sle_parallax_x_depth_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_parallax_x_depth_' + $breakpoint]['size'] : $wdt_sle_parallax_x_depth,
                        'parallaxDepthY' : ($scrollItem['wdt_sle_parallax_y_depth_' + $breakpoint] && '' != $scrollItem['wdt_sle_parallax_y_depth_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_parallax_y_depth_' + $breakpoint]['size'] : $wdt_sle_parallax_y_depth,
                        'rotateAngleX' : ($scrollItem['wdt_sle_rotate_x_angle_' + $breakpoint] && '' != $scrollItem['wdt_sle_rotate_x_angle_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_rotate_x_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_x_angle,
                        'rotateAngleY' : ($scrollItem['wdt_sle_rotate_y_angle_' + $breakpoint] && '' != $scrollItem['wdt_sle_rotate_y_angle_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_rotate_y_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_y_angle,
                        'rotateAngleZ' : ($scrollItem['wdt_sle_rotate_z_angle_' + $breakpoint] && '' != $scrollItem['wdt_sle_rotate_z_angle_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_rotate_z_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_z_angle,
                        'scaleValue' : ($scrollItem['wdt_sle_scale_value_' + $breakpoint] && '' != $scrollItem['wdt_sle_scale_value_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_scale_value_' + $breakpoint]['size'] : $wdt_sle_scale_value,
                        'blurValue' : ($scrollItem['wdt_sle_blur_value_' + $breakpoint] && '' != $scrollItem['wdt_sle_blur_value_' + $breakpoint]['size']) ? $scrollItem['wdt_sle_blur_value_' + $breakpoint]['size'] : $wdt_sle_blur_value,
                        'opacityValue' : ($scrollItem['wdt_sle_opacity_value' + $breakpoint] && '' != $scrollItem['wdt_sle_opacity_value' + $breakpoint]['size']) ? $scrollItem['wdt_sle_opacity_value' + $breakpoint]['size'] : $wdt_sle_opacity_value,
                    };
                }

            });

            return $scrollBreakpointItem;

        };

        $self.animationEffectScroll = function() {

            // Responsivewise Options
            let $scrollBreakpointwiseItem = $self.getScrollResponsiveSettings($scrollItemSettings);

            // Get settings
            if(!$scrollBreakpointwiseItem[$deviceMode]) {
                return false;
            }

            const $parallaxDirectionX = $scrollItemSettings['wdt_sle_parallax_x_direction'] ? Boolean($scrollItemSettings['wdt_sle_parallax_x_direction']) : false;
            const $parallaxDepthX = $scrollBreakpointwiseItem[$deviceMode].parallaxDepthX;
            const $parallaxDirectionY = $scrollItemSettings['wdt_sle_parallax_y_direction'] ? Boolean($scrollItemSettings['wdt_sle_parallax_y_direction']) : false;
            const $parallaxDepthY = $scrollBreakpointwiseItem[$deviceMode].parallaxDepthY;

            const $rotateX = $scrollItemSettings['wdt_sle_rotate_x'] ? Boolean($scrollItemSettings['wdt_sle_rotate_x']) : false;
            const $rotateAngleX = $scrollBreakpointwiseItem[$deviceMode].rotateAngleX;
            const $rotateY = $scrollItemSettings['wdt_sle_rotate_y'] ? Boolean($scrollItemSettings['wdt_sle_rotate_y']) : false;
            const $rotateAngleY = $scrollBreakpointwiseItem[$deviceMode].rotateAngleY;
            const $rotateZ = $scrollItemSettings['wdt_sle_rotate_z'] ? Boolean($scrollItemSettings['wdt_sle_rotate_z']) : false;
            const $rotateAngleZ = $scrollBreakpointwiseItem[$deviceMode].rotateAngleZ;

            const $scale = $scrollItemSettings['wdt_sle_scale'] ? Boolean($scrollItemSettings['wdt_sle_scale']) : false;
            const $scaleValue = $scrollBreakpointwiseItem[$deviceMode].scaleValue;

            const $blur = $scrollItemSettings['wdt_sle_blur'] ? Boolean($scrollItemSettings['wdt_sle_blur']) : false;
            const $blurValue = $scrollBreakpointwiseItem[$deviceMode].blurValue;

            const $opacity = $scrollItemSettings['wdt_sle_opacity'] ? Boolean($scrollItemSettings['wdt_sle_opacity']) : false;
            const $opacityValue = $scrollBreakpointwiseItem[$deviceMode].opacityValue;

            let $wrapper = $scrollItemSettings['wdt_item'].find('.wdt-section-bgeffects-image');
            // compute item positions
            const itemTop = +$wrapper.offset().top;
            const itemHeight = +$wrapper.height();
            const toScroll = (itemTop + itemHeight);
            const windowHeight = $window.height();
            const fromScroll = (itemTop - windowHeight);

            // Build options object (we store in DOM attr for debugging)
            let opts = {
                from: fromScroll,
                to: toScroll,
            };

            if($parallaxDirectionX) opts.x = $parallaxDepthX;
            if($parallaxDirectionY) opts.y = $parallaxDepthY;
            if($rotateX) opts.rotateX = $rotateAngleX;
            if($rotateY) opts.rotateY = $rotateAngleY;
            if($rotateZ) opts.rotateZ = $rotateAngleZ;
            if($scale) opts.scale = $scaleValue;
            if($blur) opts.blur = $blurValue;
            if($opacity) opts.opacity = $opacityValue;

            // store options as data-parallax for optional debug
            $wrapper.attr('data-parallax', JSON.stringify(opts));

            // add to scrollItems list (so global loop updates it)
            scrollItems.push({
                el: $wrapper,
                opts: opts,
                from: opts.from,
                to: opts.to,
                height: itemHeight
            });

        };

        // recompute positions (call on resize)
        $self.recalculateScrollItems = function() {
            scrollItems.forEach(function(item) {
                const el = item.el;
                const top = el.offset().top;
                const h = el.outerHeight();
                item.from = top - $window.height();
                item.to = top + h;
                // update stored opts as well if present
                if(item.opts) {
                    item.opts.from = item.from;
                    item.opts.to = item.to;
                    el.attr('data-parallax', JSON.stringify(item.opts));
                }
            });
        };

        // single rAF loop that updates all scroll items
        $self.scrollLoop = function() {
            scrollTick = false;

            const scrollY = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;

            // update each item
            scrollItems.forEach(function(item) {
                const el = item.el;
                const opts = item.opts || {};
                const from = item.from;
                const to = item.to;
                const range = (to - from) || 1;
                // compute progress 0..1
                let prog = (scrollY - from) / range;
                prog = Math.min(Math.max(prog, 0), 1);

                // compute transforms
                // translate: map prog from [-1 .. 1] -> -1 at 0, +1 at 1
                const map = (v) => (v * 2 - 1);

                let tx = 0, ty = 0, rX = 0, rY = 0, rZ = 0, scale = 1, opacity = 1, filter = '';

                if(opts.x !== undefined) {
                    tx = map(prog) * opts.x * -1; // flip direction for natural feel
                }
                if(opts.y !== undefined) {
                    ty = map(prog) * opts.y * -1;
                }
                if(opts.rotateX !== undefined) rX = map(prog) * opts.rotateX;
                if(opts.rotateY !== undefined) rY = map(prog) * opts.rotateY;
                if(opts.rotateZ !== undefined) rZ = map(prog) * opts.rotateZ;
                if(opts.scale !== undefined) scale = 1 + (opts.scale - 1) * prog;
                if(opts.opacity !== undefined) opacity = 1 + (opts.opacity - 1) * prog;
                if(opts.blur !== undefined) filter = 'blur(' + (opts.blur * (1 - Math.abs(prog - 0.5) * 2)).toFixed(2) + 'px)'; // peak blur near center

                // apply
                const transformParts = [];
                if(tx || ty) transformParts.push('translate3d(' + tx.toFixed(2) + 'px,' + ty.toFixed(2) + 'px,0)');
                if(rX) transformParts.push('rotateX(' + rX.toFixed(2) + 'deg)');
                if(rY) transformParts.push('rotateY(' + rY.toFixed(2) + 'deg)');
                if(rZ) transformParts.push('rotate(' + rZ.toFixed(2) + 'deg)');
                if(scale !== 1) transformParts.push('scale(' + parseFloat(scale).toFixed(4) + ')');

                el.css({
                    transform: transformParts.join(' '),
                    opacity: opacity
                });

                if(filter) {
                    el.css('filter', filter);
                } else {
                    el.css('filter', '');
                }
            });

            scrollRaf = requestAnimationFrame($self.scrollLoop);
        };

        $self.startScrollLoop = function() {
            if(!scrollRaf) {
                scrollRaf = requestAnimationFrame($self.scrollLoop);
            }
        };

        $self.stopScrollLoop = function() {
            if(scrollRaf) {
                cancelAnimationFrame(scrollRaf);
                scrollRaf = null;
            }
        };

        $self.destroyAll = function() {
            // mousemove cleanup
            $scope.off('.wdt_mme');
            if(mouseMoveState.raf) cancelAnimationFrame(mouseMoveState.raf);
            mouseMoveState.raf = null;
            mouseMoveState.running = false;

            // scroll cleanup
            $self.stopScrollLoop();
            scrollItems = [];
            $window.off('resize.wdtBgeffects');

            // remove generated DOM (optional: you might want to keep it, but safe to remove)
            // $scope.find('.wdt-section-bgeffects-item').remove();
        };

    };

    $(window).on('elementor/frontend/init', function () {
        elementorFrontend.hooks.addAction( 'frontend/element_ready/section', wdtSectionsOptionsHandler );
    });

})(jQuery);
