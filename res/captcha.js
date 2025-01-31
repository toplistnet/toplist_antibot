// TODO: rename modal classes and ids to be unique and not use user specific design
var grecaptcha_url = document.querySelector('script[src*="/assets/captcha.js"]').src;
grecaptcha_url = grecaptcha_url.split('?')[0];

function captcha_class() {
    this.timeout = [];
    this.callbacks = [];
}

captcha_class.prototype.renderOneElement = function(div, sitekey) {
    var element_name = 'recaptcha-' + Math.random().toString(36).substring(2, 15);
    div.setAttribute('data-element-name', element_name);

    var wrapperDiv = document.createElement('div');
    wrapperDiv.id = 'captcha_wrapper_' + element_name;

    var iframe = document.createElement('iframe');
    iframe.allowtransparency = true;
    iframe.title = 'reCAPTCHA';
    iframe.width = '304px';
    iframe.height = '78px';
    iframe.role = 'presentation';
    iframe.name = element_name;
    iframe.frameBorder = '0';
    iframe.scrolling = 'no';
    iframe.sandbox = 'allow-forms allow-same-origin allow-scripts allow-top-navigation';
    iframe.src = grecaptcha_url.replace('/assets/captcha.js', '') + '/captcha/button/' + sitekey + '?element_name=' + element_name;
    
    if (window.attachEvent) {
        document.attachEvent('onmousemove', function() {
            grecaptcha.resetCaptchaButtonTimeout(iframe, element_name);
        });
    } else {
        document.addEventListener('mousemove', function() {
            grecaptcha.resetCaptchaButtonTimeout(iframe, element_name);
        });
    }
    this.resetCaptchaButtonTimeout(iframe, element_name);

    var input = document.createElement('input');
    input.type = 'hidden';
    input.id = "g-recaptcha-response-" + element_name;
    input.name = 'g-recaptcha-response';
    input.className += ' g-recaptcha-response-' + element_name;
    input.value = '';
    input.required = true;

    wrapperDiv.appendChild(iframe);
    wrapperDiv.appendChild(input);
    div.appendChild(wrapperDiv);
    if (document.querySelector('#' + element_name) && document.querySelector('#' + element_name).addEventListener) {        
        document.querySelector('#' + element_name).addEventListener('invalid', function(event) {
            event.preventDefault();
            var iframe = this.previousSibling;
            while (iframe && iframe.nodeType !== 1) {  // Loop to find the element node
                iframe = iframe.previousSibling;
            }
            iframe.contentWindow.postMessage('shake', '*');
        });
    }
};

captcha_class.prototype.renderAll = function() {
    var recaptchaDivs = document.getElementsByClassName('g-recaptcha');
    for (var i = 0; i < recaptchaDivs.length; i++) {
        var div = recaptchaDivs[i];
        this.renderOneElement(div, div.getAttribute('data-sitekey'));
    };
}

captcha_class.prototype.render = function(container, parameters) {
    if (!container || container == null || container == undefined) {
        this.renderAll();
        return;
    }

    var div = document.querySelector("#" + container);
    if (!div || div == null || div == undefined) {
        if (typeof console !== 'undefined' && console.log)
            console.log("CAPTCHA: cant find container " + container);
        return;
    }
    
    var sitekey = null;
    if (parameters && parameters.sitekey)
        sitekey = parameters.sitekey;
    else
        sitekey = div.getAttribute('data-sitekey');

    if (parameters && parameters.callback != undefined)
        this.callbacks[div.getAttribute('data-element-name')] = parameters.callback;
        
    this.renderOneElement(div, sitekey);
}

captcha_class.prototype.reset = function(opt_widget_id) {
    if (!opt_widget_id || opt_widget_id == null || opt_widget_id == undefined)
        this.renderAll();
    else
        this.render(opt_widget_id);
}

captcha_class.prototype.getResponse = function(opt_widget_id) {
    if (!opt_widget_id || opt_widget_id == null || opt_widget_id == undefined)
        return document.querySelector('input[name="g-recaptcha-response"]').value;
    else {
        var div = document.querySelector('#' + opt_widget_id);
        var element_name = div.getAttribute('data-element-name');
        return document.querySelector("#g-recaptcha-response-" + element_name).value;
    }
}

captcha_class.prototype.resetCaptchaButtonTimeout = function(iframe, element_name) {
    if (this.timeout[element_name])
        clearTimeout(this.timeout[element_name]);

    this.timeout[element_name] = setTimeout(function () {
        iframe.src = iframe.src
        if (document.querySelector('#modal-' + element_name))
            document.querySelector('#modal-' + element_name).remove();
        grecaptcha.resetCaptchaButtonTimeout(iframe, element_name);
    }, 1000*2*2000); // 2 minutes
}

captcha_class.prototype.parseMsg = function(msg) {
    if (typeof msg !== 'string') {
        return false;
    }
    
    if (msg.indexOf('captcha_url;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        
        var url = grecaptcha_url.replace('/assets/captcha.js', parts[2]);
        url += "?element_name=" + element_name;

        var modalDiv = document.createElement('div');
        modalDiv.id = 'modal-' + element_name;
        modalDiv.style.position = 'fixed';
        modalDiv.style.top = '0';
        modalDiv.style.left = '0';
        modalDiv.style.width = '100%';
        modalDiv.style.height = '100%';
        modalDiv.style.background = 'rgba(0, 0, 0, 0.7)';
        modalDiv.style.zIndex = '9999';
        modalDiv.style.display = 'flex';
        modalDiv.style.justifyContent = 'center';
        modalDiv.style.alignItems = 'center';
        modalDiv.onclick = function() {
            document.querySelector("iframe[name='" + element_name + "']").contentWindow.postMessage('reset_captcha_checkbox;' + element_name, '*');
            document.querySelector('#modal-' + element_name).remove();
        };

        var modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.id = 'modal-id-' + element_name;
        modalContent.style.position = 'relative';
        modalContent.style.width = '0px';
        modalContent.style.height = '0px';
        modalContent.style.background = 'white';

        var closeSpan = document.createElement('span');
        closeSpan.className = 'close';
        closeSpan.style.position = 'absolute';
        closeSpan.style.fontSize = '26px';
        closeSpan.style.color = 'white';
        closeSpan.style.right = '10px';
        closeSpan.style.cursor = 'pointer';
        closeSpan.innerHTML = '&times;';
        closeSpan.onclick = function() {
            document.querySelector("iframe[name='" + element_name + "']").contentWindow.postMessage('reset_captcha_checkbox;' + element_name, '*');
            document.querySelector('#modal-' + element_name).remove();
        };

        var iframe2 = document.createElement('iframe');
        iframe2.allowTransparency = true;
        iframe2.src = url;
        iframe2.style.width = '100%';
        iframe2.style.height = '100%';
        iframe2.style.border = 'none';
        iframe2.frameBorder = '0';
        iframe2.scrolling = 'no';
        iframe2.sandbox = 'allow-forms allow-same-origin allow-scripts allow-top-navigation';

        modalContent.appendChild(closeSpan);
        modalContent.appendChild(iframe2);
        modalDiv.appendChild(modalContent);
        document.querySelector('div#captcha_wrapper_' + element_name).appendChild(modalDiv);
    }
    else if (msg.indexOf('captcha_done;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        var captcha_result = parts[2];
        document.querySelector("#g-recaptcha-response-" + element_name).value = captcha_result;
        document.querySelector('#modal-' + element_name).remove();
        clearTimeout(this.timeout[element_name]);
        if (this.callbacks[element_name] != undefined) {
            this.callbacks[element_name]();
            this.callbacks[element_name] = undefined;
        }
    }
    else if (msg.indexOf('captcha_iframe_size;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        var width = parts[2];
        var height = parts[3];
        document.querySelector("#modal-id-" + element_name).style.width = width + "px";
        document.querySelector("#modal-id-" + element_name).style.height = height + "px";
    }
    
    return false;
}

window.grecaptcha = new captcha_class();

captcha_class.prototype.grecaptcha_loader = function() {
    var url = document.querySelector('script[src*="/assets/captcha.js"]').src;
    if (url.indexOf('.js?') !== -1) {
        var parameters = url.split('?')[1];
        var parts = parameters.split('&');
        var isExplicit = false;
        var b_onload = false;
        for (var i = 0; i < parts.length; i++) {
            var key_value = parts[i].split('=');
            if (key_value[0] == 'onload') {
                if (key_value[1] != 'onload')
                    alert("recaptcha onload function name can be only named 'onload' currently.");
                else
                    b_onload = true;
            }
            else if (key_value[0] == 'render' && key_value[1] == 'explicit') {
                isExplicit = true;
            }
        }
        
        if (b_onload)
            onload();

        if (!isExplicit)
            window.grecaptcha.render();
    }
    else
        window.grecaptcha.render();

    if (window.attachEvent) {
        window.attachEvent('onmessage', function(e) {
            if (window.grecaptcha)
                window.grecaptcha.parseMsg(e.data);
            return false;
        });
    } else {
        window.addEventListener('message', function(e) {
            if (window.grecaptcha)
                window.grecaptcha.parseMsg(e.data);
            return false;
        });
    }
}

if (document.readyState === 'complete' || document.readyState === 'interactive') {
    grecaptcha.grecaptcha_loader();
} else {
    if (document.attachEvent)
        document.attachEvent('onreadystatechange', function() {
            if (document.readyState === 'complete') {
                grecaptcha.grecaptcha_loader();
            }
        });
    else
        document.addEventListener('DOMContentLoaded', function() {
            grecaptcha.grecaptcha_loader();
        });
}

captcha_class.prototype.fadeIn = function(element) {
    var opacity = 0;  // Start with fully transparent
    element.style.display = 'block';  // Make sure element is visible (if hidden)
    element.style.opacity = opacity;  // Set initial opacity
    
    // Using setInterval to increment opacity
    var interval = setInterval(function() {
        if (opacity >= 1) {
            clearInterval(interval);  // Stop when fully visible
        } else {
            opacity += 0.1;  // Increase opacity gradually
            element.style.opacity = opacity;
        }
    }, 30);  // Interval in ms (30ms for smooth transition)
}

captcha_class.prototype.fadeOut = function(element) {
    var opacity = 1;  // Start with fully visible
    element.style.opacity = opacity;  // Set initial opacity

    // Using setInterval to decrement opacity
    var interval = setInterval(function() {
        if (opacity <= 0) {
            clearInterval(interval);  // Stop when fully transparent
            element.style.display = 'none';  // Hide element after fade out is complete
        } else {
            opacity -= 0.1;  // Decrease opacity gradually
            element.style.opacity = opacity;
        }
    }, 30);  // Interval in ms (30ms for smooth transition)
}