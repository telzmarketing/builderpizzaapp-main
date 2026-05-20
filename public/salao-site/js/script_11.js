(function ($) {

    const wdtSpecificationsWidgetHandler = function($scope, $) {
  
        const $this_holder = $scope.find('.wdt-specifications-holder');

        
        var specific_wdt_column = $scope.find('.wdt-specifications-holder .wdt-column-wrapper .wdt-column');

        $scope.find('.wdt-specifications-holder .wdt-column-wrapper .wdt-column:nth-child(2)').addClass('wdt-active');
        specific_wdt_column.mouseover( function() {
            if( !($(this).hasClass('wdt-active')) ) {
                $scope.find('.wdt-specifications-holder .wdt-column-wrapper .wdt-column').removeClass('wdt-active');
            $(this).addClass('wdt-active');
            }
        });
      
  
    };
  
    $(window).on('elementor/frontend/init', function () {
          elementorFrontend.hooks.addAction('frontend/element_ready/wdt-specifications.default', wdtSpecificationsWidgetHandler);
    });
  
  })(jQuery);
  