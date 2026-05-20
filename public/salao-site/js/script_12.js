(function ($) {

const wdtFlexBannerWidgetHandler = function($scope, $) {

    var $slider_effect = $scope.find('.wdt-flex-banner-options');
    var $content_option = $slider_effect.data('settings');

    if( $content_option['option'] == 'yes' ) {
        $(".wdt-flex-banner-option").hover(function(){
            $(".wdt-flex-banner-option").removeClass("active");
            $(this).addClass("active");
        });
    } else {
        $(".wdt-flex-banner-option").click(function(){
            $(".wdt-flex-banner-option").removeClass("active");
            $(this).addClass("active");
        });
    }
    
}
            
$(window).on('elementor/frontend/init', function () {
    elementorFrontend.hooks.addAction('frontend/element_ready/wdt-flex-banner.default', wdtFlexBannerWidgetHandler);
});

})(jQuery);            
        