(function ($) {

    jQuery(document).ready(function ($) {
        var $form = $('.wdt-opentable-booking-form');
    
        if ($form.length) {
            initDatePicker($form);
        }
    
        function initDatePicker($form) {
            var $datePicker = $form.find('#hotelbookingdate');
    
            var today = new Date();
            var formatDate = function (date) {
                return date.toISOString().split('T')[0];
            };
    
            if (!$datePicker.val()) {
                $datePicker.val(formatDate(today));
            }
    
            $datePicker.datepicker({
                minDate: 0,
                numberOfMonths: 1,
                dateFormat: 'yy-mm-dd',
                showAnim: 'fadeIn',
                beforeShow: function (input, inst) {
                    setTimeout(function () {
                        var $datepicker = $(inst.dpDiv);
    
                        if (!$datepicker.parent().is('body')) {
                            $datepicker.appendTo('body');
                        }
    
                        function positionDatePicker() {
                            var $container = $(input).closest('.wdt-date-selection');
                            var inputOffset = $container.offset();
                            var inputHeight = $container.outerHeight();
                            var datepickerHeight = $datepicker.outerHeight();
    
                            var topPosition = inputOffset.top + inputHeight;
                            $datepicker.css({
                                position: 'absolute',
                                zIndex: 9999,
                                left: inputOffset.left + "px",
                                top: topPosition + "px"
                            });
                        }
    
                        positionDatePicker();
                        $(window).on('scroll resize', positionDatePicker);
                    }, 10);
                },
                onClose: function () {
                    $(window).off('scroll resize');
                }
            });
        }
    });
    

})(jQuery);