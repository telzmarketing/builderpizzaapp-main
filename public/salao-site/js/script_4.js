(function ($) {

    const wdtAnimationWidgetHandler = function($scope, $) {

      // Initialize each item with position and height

          $animation_wrapper = $scope.find('.wdt-animation-wrapper div[class*="-marqee"]');
          $animation_wrapper_width = $animation_wrapper.width();
          $animation_wrapper.css({ '--wdt-marque-width': $animation_wrapper_width+'px', '--wdt-marque-Margin-Width': '-'+$animation_wrapper_width+'px' });

    };

    $(window).on('elementor/frontend/init', function () {
          elementorFrontend.hooks.addAction('frontend/element_ready/wdt-animation.default', wdtAnimationWidgetHandler);
    });

  })(jQuery);
