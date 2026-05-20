jQuery.noConflict();
jQuery(document).ready(function($) {
    "use strict";


    if( $("#header-wrapper .sticky-header").length > 0 ) {
        
        var $sticky_header_cloned = $('#header').clone();
        $sticky_header_cloned.addClass('sticky-header-active');
        $( $sticky_header_cloned ).insertBefore( $('.wrapper') );

        $sticky_header_cloned.find('.sticky-header').addClass('sticky-header-active');
        $sticky_header_cloned.find('.sticky-header').siblings().remove();

        $('body').css('--sticky-header-height', $('.sticky-header-active').outerHeight() + 'px');

        $sticky_header_cloned.find('.wdt-header-icons-list-item.search-item.search-overlay').each(function() {
            var $searchContainer = $(this).find('.wdt-search-form-container');
            if ($searchContainer.length) {
                $searchContainer.remove(); 
            }
        });


        var position = $(window).scrollTop();

        $(window).scroll(function() {
            var scroll = $(window).scrollTop();
            if((scroll > 300 && position > 0) && scroll > position) {
                $("#header .sticky-header-active").addClass('wdt-header-top');
                $("#header .sticky-header-active").addClass('wdt-header-scroll');

                $("#header .sticky-header-active").show();
            } else {
                $("#header .sticky-header-active").removeClass('wdt-header-top');
                $("#header .sticky-header-active").removeClass('wdt-header-scroll');
            }
            position = scroll;
        });
        
    }

    // Mega Menu
    function megaMenu() {

        var $header = 0;
        var $header_width = 0;
        if( $("#header .container").length ) {
            $header = $("#header .container").offset().left;
        }
        $("li.has-mega-menu").each(function(){
            var $parent      = $(this),
                $parent_left = $parent.offset().left,
                $sub_menu    = $parent.children("ul.sub-menu"),
                $section     = $sub_menu.find('section');

            if( $section.hasClass('elementor-section-stretched') ) {

            	setTimeout(function() {
           			$sub_menu.css('left', - ( $parent_left ) );

            		var pad = $sub_menu.css('padding-left');
            		$section.css('left', - ( parseInt(pad) ) );

                    var windowWidth = $(window).width();
                    $sub_menu.css('width', parseInt( windowWidth ) );
            	}, 100);

            } else {
                $sub_menu.css('left', ( $header - $parent_left ) );
                if( !($("#header .container").length) ) {
                    $sub_menu.css('width', ( document.documentElement.clientWidth ) );
                }
                else
                {
                    var parentElement = document.querySelector("#header .container");
                    var parentElementWidth = parentElement.clientWidth;
                    $("li.has-mega-menu").find("ul.sub-menu").css('width',parentElementWidth);
                }
            }
        });
    }
    megaMenu();

    $(window).on("resize", function() {
        megaMenu();
    });
});