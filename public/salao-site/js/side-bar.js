(function ($) {
    "use strict";

    $(document).ready(function() {

        if (typeof gsap !== "undefined" && typeof ScrollSmoother !== "undefined") {

            gsap.registerPlugin(ScrollTrigger);

            gsap.timeline({
                scrollTrigger: {
                    trigger: "#primary",  
                    start: "top top+=50",
                    end: sideBarEnd(),
                    pin: ".wdt-sidebar-wrapper",
                    pinSpacing: true,
                    scrub: true
                }
            });

            function sideBarEnd() {
                if( $("#secondary").length ) {
                    var primaryHeight = $("#primary").innerHeight();
                    $("#secondary").innerHeight(primaryHeight);

                    return primaryHeight - $(".wdt-sidebar-wrapper").innerHeight();
                } else {
                    return "+=0";
                }
            }


        } else if( $("#secondary").length ) {
            $('.secondary-sidebar')
                .theiaStickySidebar({
                    additionalMarginTop: 90,
                    containerSelector: $('#primary')
                });
        }
    });
})(jQuery);