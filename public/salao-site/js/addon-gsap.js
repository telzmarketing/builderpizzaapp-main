
document.addEventListener("DOMContentLoaded", function () {

    // Get Device width

    let wdtDeviceWidth = document.documentElement.clientWidth;


    // Gsap Config

    gsap.config({ nullTargetWarn: false });

    if (typeof gsap !== "undefined" && typeof ScrollSmoother !== "undefined") {
        gsap.registerPlugin(ScrollTrigger, ScrollSmoother);

        const smoother = ScrollSmoother.create({
            wrapper: "#smooth-wrapper", 
            content: "#smooth-content",
            smooth: 1,
            effects: true,
        });

    } else {
        console.warn(":warning: GSAP or ScrollSmoother not loaded properly");
    }


    // Css Sticky Content

    var wdt_stickyColumns = document.querySelectorAll('.wdt-sticky-css-column');

    wdt_stickyColumns.forEach(function(wdt_column) {
        
        var wdt_inner__Wrapper = document.createElement('div');
        wdt_inner__Wrapper.className = 'wdt-sticky-inner-wrapper';
        
        while (wdt_column.firstChild) {
            wdt_inner__Wrapper.appendChild(wdt_column.firstChild);
        }
        wdt_column.appendChild(wdt_inner__Wrapper);
    });
    
});

  