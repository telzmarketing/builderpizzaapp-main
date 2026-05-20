(function ($) {

    const wdtTeamWidgetHandler = function($scope, $) {
      
        const $this_holder = $scope.find('.wdt-team-holder.wdt-rc-template-modern-overlay');
        
        if( $this_holder.length > 0 ) {
            
            var specific_wdt_column = $this_holder.find('.wdt-column-wrapper .wdt-column');
        
            $this_holder.find('.wdt-column-wrapper .wdt-column:nth-child(2)').addClass('wdt-active'); 

            specific_wdt_column.mouseover( function() {

                var $this = $(this);

                if( !($this.hasClass('wdt-active')) ) {
                    $this_holder.find('.wdt-column-wrapper .wdt-column').removeClass('wdt-active');
                    $this.addClass('wdt-active');

                    // $this_holder.find('.wdt-content-detail-group').show(300);
                    // $this.find('.wdt-content-detail-group').hide(300);
                
                    $this_holder.find('.wdt-content-detail-group').css('margin-bottom', '0px');

                    var $hoverDetail = $this.find('.wdt-content-detail-group').outerHeight();
                    $this.find('.wdt-content-detail-group').css({marginBottom: -($hoverDetail) + 'px'});

                }

            });

            specific_wdt_column.each( function() {    
                var $this = $(this);

                var $itemHeight = $this.find('.wdt-content-item').outerHeight();
                $this.find('.wdt-content-item').css('height', $itemHeight + 'px');
                
                if( $this.hasClass('wdt-active') ) {

                    var $defHoverDetail = $this.find('.wdt-content-detail-group').outerHeight();
                    $this.find('.wdt-content-detail-group').css({marginBottom: -($defHoverDetail) + 'px'});

                }
            });

        }
      
  
    };
  
    $(window).on('elementor/frontend/init', function () {
          elementorFrontend.hooks.addAction('frontend/element_ready/wdt-team.default', wdtTeamWidgetHandler);
    });
  
  })(jQuery);
  