(function ($) {

    const wdtWidgetsOptionsHandler = function($scope) {
        const animationEffectInstance = new wdtWidgetsAnimationEffectHandlerInit($scope);
        animationEffectInstance.init();
        const inviewInstance = new wdtWidgetsInViewHandlerInit($scope);
        inviewInstance.init();
    };

    const wdtWidgetsAnimationEffectHandlerInit = function($scope) {

        const $self   = this,
            $window   = $(window),
            $widgetId = $scope.data('id'),
            $editMode = Boolean(elementorFrontend.isEditMode()),
            $activeBreakpoints = elementorFrontend.config.responsive.activeBreakpoints,
            $deviceMode = elementorFrontend.getCurrentDeviceMode();

        let $parallaxRaf = null;
        let $parallaxState = null; // for requestAnimationFrame smoothing
        let $activeBreakpointkeys = [];
        let $animationEffectSettings = false;
        let $animationEffectBreakpointSettings = [];

        let $autoMoveElement;
        let $marqueeAnimationId;

        $self.init = function() {
            $self.animationEffectInit();
        };

        $self.animationEffectInit = function() {

            if($editMode) {
                $animationEffectSettings = $self.generateEditorSettings($widgetId);
            } else {
                $animationEffectSettings = $scope.data('settings') || false;
                $animationEffectSettings = (false !== $animationEffectSettings) ? $animationEffectSettings : false;
            }

            if(!$animationEffectSettings || $animationEffectSettings['wdt_animation_effect'] === 'none') {
                return false;
            }

            // Update breakpoints
            $self.updateActiveBreakpoints();

            // Mouse Move Effect
            if($animationEffectSettings['wdt_animation_effect'] === 'mouse-move') {
                $self.animationEffectMouseMove();
            }

            // Scroll Effect
            if($animationEffectSettings['wdt_animation_effect'] === 'scroll') {
                $self.animationEffectScroll();
            }

            // Auto Moving Effect
            if($animationEffectSettings['wdt_animation_effect'] === 'auto-movement') {
                $self.animationEffectAutoMovement();
            }

            // Marquee Effect
            if($animationEffectSettings['wdt_animation_effect'] === 'marquee') {
                $self.animationEffectMarquee();
            }

        };

        $self.generateEditorSettings = function($widgetId) {

            let $editorModels = null;
            let $editorSettings   = {};

            if(!window.elementor.hasOwnProperty('elements')) {
                return false;
            }

            $editorModels = window.elementor.elements.models;
            if(!$editorModels) {
                return false;
            }

            $.each( $editorModels, function( index, obj ) {
                $.each( obj.attributes.elements.models, function( index, obj ) {
                    $.each( obj.attributes.elements.models, function( index, obj ) {
                        if($widgetId === obj.id) {
                            $editorSettings = obj.attributes.settings.attributes;
                        }
                    });
                });
            });

            let $wdtEditorKeys = Object.keys($editorSettings).filter((key) => key.includes('wdt'));
            let $wdtEditorSettings = $wdtEditorKeys.reduce((cur, key) => { return Object.assign(cur, { [key]: $editorSettings[key] })}, {});

            let $customDirections = [];
            if($wdtEditorSettings['wdt_ame_custom_directions']) {
                $.each( $wdtEditorSettings['wdt_ame_custom_directions'].models, function( index, obj ) {
                    let $customDirection = obj.attributes;
                    $customDirections.push($customDirection);
                });
            }
            $wdtEditorSettings['wdt_ame_custom_directions'] = $customDirections;

            return $wdtEditorSettings;

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

        $self.getMouseMoveResponsiveSettings = function() {

            $activeBreakpointkeys.forEach( function( $breakpoint ) {
                if('desktop' === $breakpoint) {
                    $animationEffectBreakpointSettings[$breakpoint] = {
                        'speed' : ($animationEffectSettings['wdt_mme_speed'] && $animationEffectSettings['wdt_mme_speed']['size'] && '' != $animationEffectSettings['wdt_mme_speed']['size']) ? $animationEffectSettings['wdt_mme_speed']['size'] : 0.1,
                        'depth' : ($animationEffectSettings['wdt_mme_depth'] && $animationEffectSettings['wdt_mme_depth']['size'] && '' != $animationEffectSettings['wdt_mme_depth']['size']) ? $animationEffectSettings['wdt_mme_depth']['size'] : 1
                    };
                } else {
                    $animationEffectBreakpointSettings[$breakpoint] = {
                        'speed' : ($animationEffectSettings['wdt_mme_speed_' + $breakpoint] && $animationEffectSettings['wdt_mme_speed_' + $breakpoint]['size'] && '' != $animationEffectSettings['wdt_mme_speed_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_mme_speed_' + $breakpoint]['size'] : ($animationEffectSettings['wdt_mme_speed'] && $animationEffectSettings['wdt_mme_speed']['size'] ? $animationEffectSettings['wdt_mme_speed']['size'] : 0.1),
                        'depth' : ($animationEffectSettings['wdt_mme_depth_' + $breakpoint] && $animationEffectSettings['wdt_mme_depth_' + $breakpoint]['size'] && '' != $animationEffectSettings['wdt_mme_depth_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_mme_depth_' + $breakpoint]['size'] : ($animationEffectSettings['wdt_mme_depth'] && $animationEffectSettings['wdt_mme_depth']['size'] ? $animationEffectSettings['wdt_mme_depth']['size'] : 1)
                    };
                }
            });
        };

        $self.getAnimationContainer = function() {
            // Check if .elementor-widget-container exists
            const $widgetContainer = $scope.find('.elementor-widget-container');
            if ($widgetContainer.length > 0) {
                return $widgetContainer;
            }

            // If no container exists, check for direct children in various Elementor containers
            const $possibleContainers = $scope.find('.e-con-inner, .elementor-container, .elementor-row, .e-con');
            if ($possibleContainers.length > 0) {
                return $possibleContainers.first();
            }

            // Fallback to the widget element itself
            return $scope;
        };

        /**
         * Wraps inner content safely.
         * Accepts wrapperClass like: 'wdt-effect-mouse-move-wrapper layer' (multi classes allowed)
         * Returns the jQuery wrapper element (existing or newly created)
         */
        $self.wrapContentForAnimation = function(wrapperClass) {
            const classes = (typeof wrapperClass === 'string') ? wrapperClass.trim().split(/\s+/) : [wrapperClass];
            const primaryClass = classes[0];

            const $container = $self.getAnimationContainer();
            // look for any element that has all classes
            const selector = classes.map(c => '.' + c).join('');
            const $existingWrapper = $container.find(selector);

            // If wrapper already exists, don't wrap again
            if ($existingWrapper.length > 0) {
                return $existingWrapper.first();
            }

            // If container contents length is zero, just return container children (no wrapping)
            if ($container.contents().length === 0) {
                return $container.children();
            }

            // Perform wrapInner with a wrapper that contains all classes
            const wrapperHtml = '<div class="' + classes.join(' ') + '" />';
            $container.wrapInner(wrapperHtml);
            // return the newly created wrapper
            return $container.find('.' + primaryClass).first();
        };

        /*
         * Mouse move parallax (self-contained)
         * - uses requestAnimationFrame
         * - respects speed (friction) and depth
         * - invert option supported
         * - skips on touch/mobile devices
         */
        $self.animationEffectMouseMove = function() {

            // Responsivewise Options
            $self.getMouseMoveResponsiveSettings();

            // Get settings for current device mode
            if(!$animationEffectBreakpointSettings[$deviceMode]) {
                return false;
            }

            const $speed = parseFloat($animationEffectBreakpointSettings[$deviceMode].speed) || 0.1; // friction-like (0..1)
            const $depth = parseFloat($animationEffectBreakpointSettings[$deviceMode].depth) || 1;
            const $moveAlong = $animationEffectSettings['wdt_mme_move_along'] ? $animationEffectSettings['wdt_mme_move_along'] : 'both';
            const $invertMovement = $animationEffectSettings['wdt_mme_invert_movement'] ? Boolean($animationEffectSettings['wdt_mme_invert_movement']) : false;

            // Do not run on touch devices by default (mouse move doesn't make sense)
            const isTouch = ('ontouchstart' in window) || navigator.maxTouchPoints > 0;
            if(isTouch && !$editMode) {
                return false;
            }

            // Wrap with div to apply mouse move effect
            const $wrapper = $self.wrapContentForAnimation('wdt-effect-mouse-move-wrapper layer');
            $wrapper.attr('data-depth', $depth);

            // compute scalars based on moveAlong option
            let scalarX = 10.0, scalarY = 10.0;
            if($moveAlong === 'x-axis') {
                scalarY = 0.0;
            } else if($moveAlong === 'y-axis') {
                scalarX = 0.0;
            }

            // Apply depth multiplier
            scalarX *= $depth;
            scalarY *= $depth;

            if($invertMovement) {
                scalarX = -scalarX;
                scalarY = -scalarY;
            }

            // internal state for smoothing
            let targetX = 0, targetY = 0;
            let currentX = 0, currentY = 0;
            let lastMouseMoveTime = 0;

            // bounding element for pointer tracking - prefer the wrapper's parent (the container)
            const $bound = $wrapper.parent();

            // event handler
            function onPointerMove(e) {
                const rect = $bound[0].getBoundingClientRect();
                // get event coords (support touch)
                let clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] && e.touches[0].clientX) || 0;
                let clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] && e.touches[0].clientY) || 0;

                // normalize to -1 .. 1 relative to center
                const relX = ((clientX - rect.left) / rect.width) * 2 - 1;
                const relY = ((clientY - rect.top) / rect.height) * 2 - 1;

                // targets
                targetX = relX * scalarX;
                targetY = relY * scalarY;

                lastMouseMoveTime = Date.now();
            }

            // Smooth lerp
            function lerp(a, b, t) { return a + (b - a) * t; }

            // animation loop
            function parallaxLoop() {
                // ease factor derived from $speed: higher speed means quicker response
                // transform $speed into interpolation factor: e.g. speed 0.1 => t=0.1, speed 0.5 => t=0.5
                const t = Math.min(Math.max($speed, 0.01), 0.95);

                currentX = lerp(currentX, targetX, t);
                currentY = lerp(currentY, targetY, t);

                // apply transform
                const transform = 'translate3d(' + currentX.toFixed(2) + 'px,' + currentY.toFixed(2) + 'px,0)';
                $wrapper.css('transform', transform);

                $parallaxRaf = window.requestAnimationFrame(parallaxLoop);
            }

            // start/stop helpers
            function startParallax() {
                if(!$parallaxRaf) {
                    $parallaxRaf = requestAnimationFrame(parallaxLoop);
                }
            }
            function stopParallax() {
                if($parallaxRaf) {
                    cancelAnimationFrame($parallaxRaf);
                    $parallaxRaf = null;
                }
                // reset transform
                $wrapper.css('transform', '');
                targetX = targetY = currentX = currentY = 0;
            }

            // pointer events on bound element
            $bound.on('mousemove.wdt_mme touchmove.wdt_mme', onPointerMove);

            // start parallax when mouse enters, stop when leaves (to reduce work)
            $bound.on('mouseenter.wdt_mme touchstart.wdt_mme', function() {
                startParallax();
            });
            $bound.on('mouseleave.wdt_mme touchend.wdt_mme touchcancel.wdt_mme', function() {
                // smoothly return to center
                targetX = 0;
                targetY = 0;
                // allow a few frames to settle, then stop
                setTimeout(() => {
                    // if target and current are near zero, stop to save CPU
                    if(Math.abs(currentX) < 0.5 && Math.abs(currentY) < 0.5) {
                        stopParallax();
                    }
                }, 250);
            });

            // If Elementor destroys the widget or we navigate away, cleanup listeners
            $scope.on('destroy', function() {
                $bound.off('.wdt_mme');
                stopParallax();
            });

            // In editor mode start immediately (so preview shows effect)
            if($editMode) {
                startParallax();
            }
        };

        $self.getScrollResponsiveSettings = function() {

            let $wdt_sle_parallax_x_depth = ($animationEffectSettings['wdt_sle_parallax_x_depth'] && '' != $animationEffectSettings['wdt_sle_parallax_x_depth']['size']) ? $animationEffectSettings['wdt_sle_parallax_x_depth']['size'] : 50;
            let $wdt_sle_parallax_y_depth = ($animationEffectSettings['wdt_sle_parallax_y_depth'] && '' != $animationEffectSettings['wdt_sle_parallax_y_depth']['size']) ? $animationEffectSettings['wdt_sle_parallax_y_depth']['size'] : 50;
            let $wdt_sle_rotate_x_angle = ($animationEffectSettings['wdt_sle_rotate_x_angle'] && '' != $animationEffectSettings['wdt_sle_rotate_x_angle']['size']) ? $animationEffectSettings['wdt_sle_rotate_x_angle']['size'] : 45;
            let $wdt_sle_rotate_y_angle = ($animationEffectSettings['wdt_sle_rotate_y_angle'] && '' != $animationEffectSettings['wdt_sle_rotate_y_angle']['size']) ? $animationEffectSettings['wdt_sle_rotate_y_angle']['size'] : 45;
            let $wdt_sle_rotate_z_angle = ($animationEffectSettings['wdt_sle_rotate_z_angle'] && '' != $animationEffectSettings['wdt_sle_rotate_z_angle']['size']) ? $animationEffectSettings['wdt_sle_rotate_z_angle']['size'] : 45;
            let $wdt_sle_scale_value = ($animationEffectSettings['wdt_sle_scale_value'] && '' != $animationEffectSettings['wdt_sle_scale_value']['size']) ? $animationEffectSettings['wdt_sle_scale_value']['size'] : 1;
            let $wdt_sle_blur_value = ($animationEffectSettings['wdt_sle_blur_value'] && '' != $animationEffectSettings['wdt_sle_blur_value']['size']) ? $animationEffectSettings['wdt_sle_blur_value']['size'] : 0;
            let $wdt_sle_opacity_value = ($animationEffectSettings['wdt_sle_opacity_value'] && '' != $animationEffectSettings['wdt_sle_opacity_value']['size']) ? $animationEffectSettings['wdt_sle_opacity_value']['size'] : 1;

            $activeBreakpointkeys.forEach( function( $breakpoint ) {

                if('desktop' === $breakpoint) {
                    $animationEffectBreakpointSettings[$breakpoint] = {
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
                    $animationEffectBreakpointSettings[$breakpoint] = {
                        'parallaxDepthX' : ($animationEffectSettings['wdt_sle_parallax_x_depth_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_parallax_x_depth_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_parallax_x_depth_' + $breakpoint]['size'] : $wdt_sle_parallax_x_depth,
                        'parallaxDepthY' : ($animationEffectSettings['wdt_sle_parallax_y_depth_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_parallax_y_depth_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_parallax_y_depth_' + $breakpoint]['size'] : $wdt_sle_parallax_y_depth,
                        'rotateAngleX' : ($animationEffectSettings['wdt_sle_rotate_x_angle_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_rotate_x_angle_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_rotate_x_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_x_angle,
                        'rotateAngleY' : ($animationEffectSettings['wdt_sle_rotate_y_angle_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_rotate_y_angle_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_rotate_y_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_y_angle,
                        'rotateAngleZ' : ($animationEffectSettings['wdt_sle_rotate_z_angle_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_rotate_z_angle_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_rotate_z_angle_' + $breakpoint]['size'] : $wdt_sle_rotate_z_angle,
                        'scaleValue' : ($animationEffectSettings['wdt_sle_scale_value_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_scale_value_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_scale_value_' + $breakpoint]['size'] : $wdt_sle_scale_value,
                        'blurValue' : ($animationEffectSettings['wdt_sle_blur_value_' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_blur_value_' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_blur_value_' + $breakpoint]['size'] : $wdt_sle_blur_value,
                        'opacityValue' : ($animationEffectSettings['wdt_sle_opacity_value' + $breakpoint] && '' != $animationEffectSettings['wdt_sle_opacity_value' + $breakpoint]['size']) ? $animationEffectSettings['wdt_sle_opacity_value' + $breakpoint]['size'] : $wdt_sle_opacity_value,
                    };
                }

            });

        };

        $self.animationEffectScroll = function() {

            // Responsivewise Options
            $self.getScrollResponsiveSettings();

            // Get settings
            if(!$animationEffectBreakpointSettings[$deviceMode]) {
                return false;
            }

            // Wrap with div to apply scroll effect
            const $wrapper = $self.wrapContentForAnimation('wdt-effect-scroll-wrapper');

            const $parallaxDirectionX = $animationEffectSettings['wdt_sle_parallax_x_direction'] ? Boolean($animationEffectSettings['wdt_sle_parallax_x_direction']) : false;
            const $parallaxDepthX = $animationEffectBreakpointSettings[$deviceMode].parallaxDepthX;
            const $parallaxDirectionY = $animationEffectSettings['wdt_sle_parallax_y_direction'] ? Boolean($animationEffectSettings['wdt_sle_parallax_y_direction']) : false;
            const $parallaxDepthY = $animationEffectBreakpointSettings[$deviceMode].parallaxDepthY;

            const $rotateX = $animationEffectSettings['wdt_sle_rotate_x'] ? Boolean($animationEffectSettings['wdt_sle_rotate_x']) : false;
            const $rotateAngleX = $animationEffectBreakpointSettings[$deviceMode].rotateAngleX;
            const $rotateY = $animationEffectSettings['wdt_sle_rotate_y'] ? Boolean($animationEffectSettings['wdt_sle_rotate_y']) : false;
            const $rotateAngleY = $animationEffectBreakpointSettings[$deviceMode].rotateAngleY;
            const $rotateZ = $animationEffectSettings['wdt_sle_rotate_z'] ? Boolean($animationEffectSettings['wdt_sle_rotate_z']) : false;
            const $rotateAngleZ = $animationEffectBreakpointSettings[$deviceMode].rotateAngleZ;

            const $scale = $animationEffectSettings['wdt_sle_scale'] ? Boolean($animationEffectSettings['wdt_sle_scale']) : false;
            const $scaleValue = $animationEffectBreakpointSettings[$deviceMode].scaleValue;

            const $blur = $animationEffectSettings['wdt_sle_blur'] ? Boolean($animationEffectSettings['wdt_sle_blur']) : false;
            const $blurValue = $animationEffectBreakpointSettings[$deviceMode].blurValue;

            const $opacity = $animationEffectSettings['wdt_sle_opacity'] ? Boolean($animationEffectSettings['wdt_sle_opacity']) : false;
            const $opacityValue = $animationEffectBreakpointSettings[$deviceMode].opacityValue;

            const $itemTop = +$wrapper.offset().top;
            const $itemHeight = +$wrapper.height();
            const $toScroll = ($itemTop + $itemHeight);
            const $windowHeight = $window.height();
            const $fromScroll = ($itemTop - $windowHeight);

            // Build options json
            let $options = {'distance': 10, 'smoothness': 0, 'from-scroll': $fromScroll, 'to-scroll': $toScroll};
            if($parallaxDirectionX) {
                $options['x'] = $parallaxDepthX;
            }
            if($parallaxDirectionY) {
                $options['y'] = $parallaxDepthY;
            }
            if($rotateX) {
                $options['rotateX'] = $rotateAngleX;
            }
            if($rotateY) {
                $options['rotateY'] = $rotateAngleY;
            }
            if($rotateZ) {
                $options['rotateZ'] = $rotateAngleZ;
            }
            if($scale) {
                $options['scale'] = $scaleValue;
            }
            if($blur) {
                $options['blur'] = $blurValue;
            }
            if($opacity) {
                $options['opacity'] = $opacityValue;
            }

            // Init parallax
            $wrapper.attr('data-parallax', JSON.stringify($options));

        };

        $self.autoMovementOnIntersect = function(entries, $observer) {
            entries.forEach((entry) => {
                if(entry.isIntersecting) {
                    if($autoMoveElement && typeof $autoMoveElement.play === 'function') {
                        $autoMoveElement.play();
                    }
                } else {
                    if($autoMoveElement && typeof $autoMoveElement.pause === 'function') {
                        $autoMoveElement.pause();
                    }
                }
            });
        }

        $self.generateResponsiveRandomPoints = function($direction) {

            let $reponsiveRandoms = {};

            let $wdt_x_depth = ($direction['wdt_x_depth'] && '' != $direction['wdt_x_depth']['size']) ? $direction['wdt_x_depth']['size'] : 0;
            let $wdt_y_depth = ($direction['wdt_y_depth'] && '' != $direction['wdt_y_depth']['size']) ? $direction['wdt_y_depth']['size'] : 0;
            let $wdt_rotate_angle = ($direction['wdt_rotate_angle'] && '' != $direction['wdt_rotate_angle']['size']) ? $direction['wdt_rotate_angle']['size'] : 0;
            let $wdt_scale_value = ($direction['wdt_scale_value'] && '' != $direction['wdt_scale_value']['size']) ? $direction['wdt_scale_value']['size'] : 1;
            let $wdt_blur_value = ($direction['wdt_blur_value'] && '' != $direction['wdt_blur_value']['size']) ? $direction['wdt_blur_value']['size'] : 0;
            let $wdt_opacity_value = ($direction['wdt_opacity_value'] && '' != $direction['wdt_opacity_value']['size']) ? $direction['wdt_opacity_value']['size'] : 1;

            $activeBreakpointkeys.forEach( function( $breakpoint ) {

                if('desktop' === $breakpoint) {
                    $reponsiveRandoms[$breakpoint] = {
                        'depthX'      : $wdt_x_depth,
                        'depthY'      : $wdt_y_depth,
                        'rotateAngle' : $wdt_rotate_angle,
                        'scaleValue'  : $wdt_scale_value,
                        'blurValue'   : $wdt_blur_value,
                        'opacityValue': $wdt_opacity_value
                    };
                } else {
                    $reponsiveRandoms[$breakpoint] = {
                        'depthX' : ($direction['wdt_x_depth_' + $breakpoint] && '' != $direction['wdt_x_depth_' + $breakpoint]['size']) ? $direction['wdt_x_depth_' + $breakpoint]['size'] : $wdt_x_depth,
                        'depthY' : ($direction['wdt_y_depth_' + $breakpoint] && '' != $direction['wdt_y_depth_' + $breakpoint]['size']) ? $direction['wdt_y_depth_' + $breakpoint]['size'] : $wdt_y_depth,
                        'rotateAngle' : ($direction['wdt_rotate_angle_' + $breakpoint] && '' != $direction['wdt_rotate_angle_' + $breakpoint]['size']) ? $direction['wdt_rotate_angle_' + $breakpoint]['size'] : $wdt_rotate_angle,
                        'scaleValue' : ($direction['wdt_scale_value_' + $breakpoint] && '' != $direction['wdt_scale_value_' + $breakpoint]['size']) ? $direction['wdt_scale_value_' + $breakpoint]['size'] : $wdt_scale_value,
                        'blurValue' : ($direction['wdt_blur_value_' + $breakpoint] && '' != $direction['wdt_blur_value_' + $breakpoint]['size']) ? $direction['wdt_blur_value_' + $breakpoint]['size'] : $wdt_blur_value,
                        'opacityValue' : ($direction['wdt_opacity_value' + $breakpoint] && '' != $direction['wdt_opacity_value' + $breakpoint]['size']) ? $direction['wdt_opacity_value' + $breakpoint]['size'] : $wdt_opacity_value,
                    };
                }

            });

            return $reponsiveRandoms;

        };

        $self.generateRandomPoints = function($ameCustomDirections) {

            let $points = [];

            $ameCustomDirections.forEach(($direction) => {

                let $unitPoint = {};

                const $responsiveDirections = $self.generateResponsiveRandomPoints($direction);

                // Transform
                    $unitPoint = {
                        transform: ''
                    };

                    const $xDirection = $direction['wdt_x_direction'] ? Boolean($direction['wdt_x_direction']) : false;
                    const $depthX = $responsiveDirections[$deviceMode].depthX;
                    const $yDirection = $direction['wdt_y_direction'] ? Boolean($direction['wdt_y_direction']) : false;
                    const $depthY = $responsiveDirections[$deviceMode].depthY;
                    const $rotate = $direction['wdt_rotate'] ? Boolean($direction['wdt_rotate']) : false;
                    const $rotateAngle = $responsiveDirections[$deviceMode].rotateAngle;
                    const $scale = $direction['wdt_scale'] ? Boolean($direction['wdt_scale']) : false;
                    const $scaleValue = $responsiveDirections[$deviceMode].scaleValue;

                    if($xDirection) {
                        $unitPoint['transform'] += 'translateX('+$depthX+'px) ';
                    }
                    if($yDirection) {
                        $unitPoint['transform'] += 'translateY('+$depthY+'px) ';
                    }
                    if($rotate) {
                        $unitPoint['transform'] += 'rotate('+$rotateAngle+'deg) ';
                    }
                    if($scale) {
                        $unitPoint['transform'] += 'scale('+$scaleValue+') ';
                    }

                    $unitPoint['transform'] = $.trim($unitPoint['transform'])
                    $unitPoint['opacity'] = 0.2;

                // Blur
                    const $blur = $direction['wdt_blur'] ? Boolean($direction['wdt_blur']) : false;
                    const $blurValue = $responsiveDirections[$deviceMode].blurValue;

                    if($blur) {
                        $unitPoint['filter'] = 'blur('+$blurValue+'px)';
                    }

                // Opacity
                    const $opacity = $direction['wdt_opacity'] ? Boolean($direction['wdt_opacity']) : false;
                    const $opacityValue = $responsiveDirections[$deviceMode].opacityValue;

                    if($opacity) {
                        $unitPoint['opacity'] = +$opacityValue;
                    }


                if($unitPoint) {
                    $points.push($unitPoint);
                }

            });

            return $points;

        }

        $self.animationEffectAutoMovement = function() {

            // Wrap with auto movement div
                const $wrapper = $self.wrapContentForAnimation('wdt-effect-auto-movement-wrapper');

            // Animation
                let $autoMoveElementItem = $wrapper[0];
                let $ameDirection = $animationEffectSettings['wdt_ame_direction'];
                let $ameDuration = $animationEffectSettings['wdt_ame_duration'] && $animationEffectSettings['wdt_ame_duration']['size'] ? Math.ceil($animationEffectSettings['wdt_ame_duration']['size']*1500) : 10000;
                let $ameIteration = ($animationEffectSettings['wdt_ame_iteration'] === 'infinity') ? Infinity : 1;
                let $boundTo = $animationEffectSettings['wdt_bound_to'] ? $animationEffectSettings['wdt_bound_to'] : 'section';
                let $boundToElement = ($boundTo === 'section') ? $scope.parents('.elementor-section') : $scope.parents('.elementor-column');

                let $itemWidth = +$wrapper.width();
                let $sectionWidth = +$boundToElement.width();
                let $sectionItemWidth = +$sectionWidth + +$itemWidth;

                let $itemHeight = +$wrapper.height();
                let $sectionHeight = +$boundToElement.height();
                let $sectionItemHeight = +$sectionHeight + +$itemHeight;

                if($ameDirection === 'left-to-right') {
                    $autoMoveElement = $autoMoveElementItem.animate([
                            { transform: 'translateX(-'+$itemWidth+'px)' },
                            { transform: 'translateX('+$sectionWidth+'px)' }
                        ], {
                        duration: $ameDuration,
                        iterations: $ameIteration
                    });
                    $autoMoveElement.pause();
                } else if($ameDirection === 'right-to-left') {
                    $autoMoveElement = $autoMoveElementItem.animate([
                            { transform: 'translateX('+$sectionItemWidth+'px)' },
                            { transform: 'translateX(-'+$itemWidth+'px)' }
                        ], {
                        duration: $ameDuration,
                        iterations: $ameIteration
                    });
                    $autoMoveElement.pause();
                } else if($ameDirection === 'top-to-bottom') {
                    $autoMoveElement = $autoMoveElementItem.animate([
                            { transform: 'translateY(-'+$itemHeight+'px)' },
                            { transform: 'translateY('+$sectionHeight+'px)' }
                        ], {
                        duration: $ameDuration,
                        iterations: $ameIteration
                    });
                    $autoMoveElement.pause();
                } else if($ameDirection === 'bottom-to-top') {
                    $autoMoveElement = $autoMoveElementItem.animate([
                            { transform: 'translateY('+$sectionItemHeight+'px)' },
                            { transform: 'translateY(-'+$itemHeight+'px)' }
                        ], {
                        duration: $ameDuration,
                        iterations: $ameIteration
                    });
                    $autoMoveElement.pause();
                } else if($ameDirection === 'custom') {

                    let $ameCustomDirections = $animationEffectSettings['wdt_ame_custom_directions'] || [];
                    if($ameCustomDirections.length) {
                        let $ameCustomDirectionPoints = $self.generateRandomPoints($ameCustomDirections);
                        $autoMoveElement = $autoMoveElementItem.animate($ameCustomDirectionPoints, {
                            duration: $ameDuration,
                            iterations: $ameIteration
                        });
                        $autoMoveElement.pause();
                    }

                }

            // If the widget is in view port init animation
                if('IntersectionObserver' in window) {
                    let $observer;
                    let $observerOptions = {
                        root: null,
                        rootMargin: "0px",
                        threshold: 0.1
                    };

                    $observer = new IntersectionObserver($self.autoMovementOnIntersect, $observerOptions);
                    $observer.observe($scope[0]);
                } else {
                    if($autoMoveElement && typeof $autoMoveElement.play === 'function') {
                        $autoMoveElement.play();
                    }
                }

        };

        $self.animationEffectMarquee = function() {
            // Wrap with marquee wrapper
            const $wrapper = $self.wrapContentForAnimation('wdt-effect-marquee-wrapper');

            // Animation settings
            let $width = $animationEffectSettings['wdt_mqe_width'] && $animationEffectSettings['wdt_mqe_width']['size'] ? $animationEffectSettings['wdt_mqe_width']['size'] + 'px' : '200px';
            let $height = $animationEffectSettings['wdt_mqe_height'] && $animationEffectSettings['wdt_mqe_height']['size'] ? $animationEffectSettings['wdt_mqe_height']['size'] + 'px' : '120px';
            let $speed = $animationEffectSettings['wdt_mqe_speed'] && $animationEffectSettings['wdt_mqe_speed']['size'] ? $animationEffectSettings['wdt_mqe_speed']['size'] : 1;
            let $direction = $animationEffectSettings['wdt_mqe_direction'] ? $animationEffectSettings['wdt_mqe_direction'] : 'left-to-right';
            let $boundTo = $animationEffectSettings['wdt_mqe_bound_to'] ? $animationEffectSettings['wdt_mqe_bound_to'] : 'section';

            // Find the bounding element
            let $boundToElement;
            if($boundTo === 'section') {
                $boundToElement = $scope.parents('.elementor-section').first();
            } else if($boundTo === 'container') {
                $boundToElement = $scope.parents('.e-con').first();
            } else {
                $boundToElement = $scope.parents('.elementor-column').first();
            }

            // If no bound element found, use the nearest parent with width
            if(!$boundToElement.length) {
                $boundToElement = $scope.parent();
            }

            // Style the wrapper
            $wrapper.css({
                'position': 'absolute',
                'width': $width,
                'height': $height,
                'z-index': 999
            });

            const $itemWidth = $wrapper.outerWidth();
            const $itemHeight = $wrapper.outerHeight();
            const $parentWidth = $boundToElement.width();
            const $parentHeight = $boundToElement.height();

            // Stop any existing animation
            if($marqueeAnimationId) {
                cancelAnimationFrame($marqueeAnimationId);
            }

            if($direction === 'right-to-left') {
                // Start from right side
                $wrapper.css('left', $parentWidth + 'px');
                let $currentPosition = $parentWidth;

                function animateRightToLeft() {
                    $currentPosition -= $speed;
                    $wrapper.css('left', $currentPosition + 'px');

                    // Reset when completely off screen to the left
                    if($currentPosition < -$itemWidth) {
                        $currentPosition = $parentWidth;
                    }

                    $marqueeAnimationId = requestAnimationFrame(animateRightToLeft);
                }

                $marqueeAnimationId = requestAnimationFrame(animateRightToLeft);

            } else if($direction === 'left-to-right') {
                // Start from left side
                $wrapper.css('left', -$itemWidth + 'px');
                let $currentPosition = -$itemWidth;

                function animateLeftToRight() {
                    $currentPosition += $speed;
                    $wrapper.css('left', $currentPosition + 'px');

                    // Reset when completely off screen to the right
                    if($currentPosition > $parentWidth) {
                        $currentPosition = -$itemWidth;
                    }

                    $marqueeAnimationId = requestAnimationFrame(animateLeftToRight);
                }

                $marqueeAnimationId = requestAnimationFrame(animateLeftToRight);

            } else if($direction === 'top-to-bottom') {
                // Start from top
                $wrapper.css('top', -$itemHeight + 'px');
                let $currentPosition = -$itemHeight;

                function animateTopToBottom() {
                    $currentPosition += $speed;
                    $wrapper.css('top', $currentPosition + 'px');

                    // Reset when completely off screen to the bottom
                    if($currentPosition > $parentHeight) {
                        $currentPosition = -$itemHeight;
                    }

                    $marqueeAnimationId = requestAnimationFrame(animateTopToBottom);
                }

                $marqueeAnimationId = requestAnimationFrame(animateTopToBottom);

            } else if($direction === 'bottom-to-top') {
                // Start from bottom
                $wrapper.css('top', $parentHeight + 'px');
                let $currentPosition = $parentHeight;

                function animateBottomToTop() {
                    $currentPosition -= $speed;
                    $wrapper.css('top', $currentPosition + 'px');

                    // Reset when completely off screen to the top
                    if($currentPosition < -$itemHeight) {
                        $currentPosition = $parentHeight;
                    }

                    $marqueeAnimationId = requestAnimationFrame(animateBottomToTop);
                }

                $marqueeAnimationId = requestAnimationFrame(animateBottomToTop);
            }

            // Clean up on widget destroy
            $scope.on('destroy', function() {
                if($marqueeAnimationId) {
                    cancelAnimationFrame($marqueeAnimationId);
                }
            });
        };

    };

    const wdtWidgetsInViewHandlerInit = function($scope) {

        const $self   = this,
            $window   = $(window),
            $widgetId = $scope.data('id'),
            $editMode = Boolean(elementorFrontend.isEditMode());

        let $inViewSettings = false;
        let $inViewLoop = false;
        let $inViewElement = $scope[0];

        $self.init = function() {
            $self.inViewStatusUpdateInit();
        };

        $self.inViewStatusUpdateInit = function() {

            if($editMode) {
                $inViewSettings = $self.generateEditorSettings($widgetId);
            } else {
                $inViewSettings = $scope.data('settings') || false;
                $inViewSettings = (false !== $inViewSettings) ? $inViewSettings : false;
            }

            if(!$inViewSettings || !$inViewSettings['wdt_enable_inview_status']) {
                return false;
            }

            if($inViewSettings['wdt_enable_inview_status']){
                $scope.addClass("wdt-inview-section");
            }

            $inViewLoop = $inViewSettings['wdt_enable_inview_loop'];

            if('IntersectionObserver' in window) {
                $self.createObserver();
            }

        };

        $self.generateEditorSettings = function($widgetId) {

            let $editorModels = null;
            let $editorSettings   = {};

            if(!window.elementor.hasOwnProperty('elements')) {
                return false;
            }

            $editorModels = window.elementor.elements.models;
            if(!$editorModels) {
                return false;
            }

            $.each( $editorModels, function( index, obj ) {
                $.each( obj.attributes.elements.models, function( index, obj ) {
                    $.each( obj.attributes.elements.models, function( index, obj ) {
                        if($widgetId === obj.id) {
                            $editorSettings = obj.attributes.settings.attributes;
                        }
                    });

                });
            });

            let $wdtEditorKeys = Object.keys($editorSettings).filter((key) => key.includes('wdt'));
            let $wdtEditorSettings = $wdtEditorKeys.reduce((cur, key) => { return Object.assign(cur, { [key]: $editorSettings[key] })}, {});

            return $wdtEditorSettings;

        };

        $self.createObserver = function() {
            let $observer;

            let $options = {
              root: null,
              rootMargin: "0px",
              threshold: 1
            };

            $observer = new IntersectionObserver($self.handleIntersect, $options);
            $observer.observe($inViewElement);
        }

        $self.handleIntersect= function(entries, $observer) {
            entries.forEach((entry) => {
                if(entry.isIntersecting) {
                    entry.target.classList.add('wdt-item-is-inview');
                } else {
                    if($inViewLoop) {
                        entry.target.classList.remove('wdt-item-is-inview');
                    }
                }
            });
        }

    };

    $(window).on('elementor/frontend/init', function () {
        elementorFrontend.hooks.addAction( 'frontend/element_ready/widget', wdtWidgetsOptionsHandler );
    });

})(jQuery);
