(function ($) {

  const wdtImageBoxWidgetHandler = function($scope) {
    const instance = new wdtImageBoxWidgetHandlerInit($scope);
    if($scope.find('.wdt-image-box-holder').data('settings')) {
      const settings = $scope.find('.wdt-image-box-holder').data('settings');
      if(settings['enable_popup']) {
        instance.init();
      }
      
      if(settings['enable_hover_class']) {
        instance.hover_active_class();
      }
    }



    const $image_box_modern = $scope.find('.wdt-rc-template-modern-template');


    setTimeout(function() {

      $image_box_modern.each(function() {

          var $this = $(this);
          var $this_item = $this.find('.wdt-content-item');

          var $this_content_item_merge = [];

          $this_item.each(function() {

              var $this_content_item = $(this);
              var $this_image = $this_content_item.find('.wdt-content-media-group').outerHeight();
              var $this_content = $this_content_item.find('.wdt-content-detail-group').outerHeight();

              var $common_height = Math.max($this_image, $this_content);

              $this_content_item.find('.wdt-content-media-group').outerHeight($common_height);
              $this_content_item.find('.wdt-content-detail-group').outerHeight($common_height);

              $this_content_item_merge.push(...$this_content_item.find('.wdt-content-detail-group'));

          });

          $this_content_item_merge.forEach(function(item, index) {

              if( index % 2 == 0 ) {
                  $(item).closest('.wdt-content-item').addClass('wdt-even');
                  $(item).css({
                      'order': '-1',
                      'align-items': 'end'
                  });
              } else {
                  $(item).closest('.wdt-content-item').addClass('wdt-odd');
                  $(item).css({'align-items': 'start' });
              }

          });
          
      });
    }, 500);

    try {
      
      const $imagePlaceNav = $scope.find('.wdt-rc-template-place-navigate-style');
      const $imagePlaceNavIcon = $imagePlaceNav.find('.wdt-content-item');

      $imagePlaceNavIcon.each(function() {
        const $this = $(this);
        const $itemLink = $this.find('.wdt-content-title a')[0].href;
        const $linkItem = $this.find('.wdt-content-icon');

        $linkItem.on('click', function() {
          window.location.href = $itemLink;
        });
      });

    } catch (error) {
      console.log(error);      
    }





  };

  const wdtImageBoxWidgetHandlerInit = function($scope) {

    const $self = this;
    $self.init = function() {

      const $image_box_content_repeater = $scope.find('.wdt-content-image-wrapper');
      $image_box_content_repeater.each(function() {
  
        const $this_image_box = $(this);
        const $image_url = $this_image_box.find('img').attr('src');
        $self.onClickInit($this_image_box, $image_url);

      });

    };

    $self.onClickInit = function($this_image_box, $image_url) {

      $this_image_box.magnificPopup({
        items: {
          src: $image_url,
          type: 'image',
        },
        removalDelay: 500,
        showCloseBtn: true,
        enableEscapeKey: true,
        closeOnBgClick: true,
        mainClass: 'wdt-image-box-popup wdt-popup-box-window',
      });

    };

    $self.hover_active_class = function(){

      var $get_scope_name = $scope.find('.wdt-image-box-holder').hasClass('wdt-carousel-holder');

      if( $get_scope_name ) {

        var image_box_wdt_swiper = $scope.find('.wdt-image-box-holder .wdt-image-box-container .wdt-image-box-wrapper .swiper-slide');

        $scope.find('.wdt-image-box-holder .wdt-image-box-container .wdt-image-box-wrapper .swiper-slide:first-child').addClass('wdt-active');
        image_box_wdt_swiper.mouseover( function() {
          if( !($(this).hasClass('wdt-active')) ) {
            $scope.find('.wdt-image-box-holder .wdt-image-box-container .wdt-image-box-wrapper .swiper-slide').removeClass('wdt-active');
            $(this).addClass('wdt-active');
          }
        } );

      } else {

        var image_box_wdt_column = $scope.find('.wdt-image-box-holder .wdt-column-wrapper .wdt-column');

        $scope.find('.wdt-image-box-holder .wdt-column-wrapper .wdt-column:first-child').addClass('wdt-active');
        image_box_wdt_column.mouseover( function() {
          if( !($(this).hasClass('wdt-active')) ) {
            $scope.find('.wdt-image-box-holder .wdt-column-wrapper .wdt-column').removeClass('wdt-active');
            $(this).addClass('wdt-active');
          }
        } );

      }      

    };

  };

  $(window).on('elementor/frontend/init', function () {
		elementorFrontend.hooks.addAction('frontend/element_ready/wdt-image-box.default', wdtImageBoxWidgetHandler);
  });

})(jQuery);
