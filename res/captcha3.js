function CaptchaRender() {
    document.querySelectorAll('.g-recaptcha').forEach(function(div) {
        const element_name = 'recaptcha-' + Math.random().toString(36).substring(2, 15);
        const sitekey = div.getAttribute('data-sitekey');
        const wrapperDiv = document.createElement('div');
        wrapperDiv.id = 'captcha_wrapper_' + element_name;

        const iframe = document.createElement('iframe');
        iframe.allowtransparency = true;
        iframe.title = 'reCAPTCHA';
        iframe.width = '304px';
        iframe.height = '78px';
        iframe.role = 'presentation';
        iframe.name = element_name;
        iframe.frameBorder = '0';
        iframe.scrolling = 'no';
        iframe.sandbox = 'allow-forms allow-same-origin allow-scripts allow-top-navigation allow-modals allow-storage-access-by-user-activation';
        // for easier debug domain stuff
        const captcha_url = document.querySelector('script[src$="/assets/captcha3.js"]').src.replace('/assets/captcha3.js', '');
        iframe.src = captcha_url + '/captcha/button/' + sitekey + '?element_name=' + element_name;
        
        if (window.attachEvent) {
            document.attachEvent('onmousemove', function() {
                resetCaptchaButtonTimeout(iframe, element_name);
            });
        }
        else {
            document.addEventListener('mousemove', function() {
                resetCaptchaButtonTimeout(iframe, element_name);
            });
        }
        resetCaptchaButtonTimeout(iframe, element_name);

        const input = document.createElement('input');
        input.type = 'hidden';
        input.id = element_name;
        input.name = 'g-recaptcha-response';
        input.value = '';
        input.required = true;

        wrapperDiv.appendChild(iframe);
        wrapperDiv.appendChild(input);
        div.appendChild(wrapperDiv);
        if (document.querySelector('#' + element_name) && document.querySelector('#' + element_name).addEventListener)
            document.querySelector('#' + element_name).addEventListener('invalid', function(event) {
                event.preventDefault();
                const iframe = this.previousElementSibling;
                iframe.contentWindow.postMessage('shake', '*');
            });
    });
}

if (document.readyState === 'complete' || document.readyState === 'interactive') {
    CaptchaRender();
} else {
    if (document.attachEvent)
        document.attachEvent('onreadystatechange', function() {
            if (document.readyState === 'complete') {
                CaptchaRender();
            }
        });
    else
        document.addEventListener('DOMContentLoaded', function() {
            CaptchaRender();
        });
}

var timeout = 0; // TODO: maybe not working on multiple captcha buttons
function resetCaptchaButtonTimeout(iframe, element_name) {
    if (timeout)
        clearTimeout(timeout);

    timeout = setTimeout(function () {
        iframe.src = iframe.src
        if (document.querySelector('#modal-' + element_name))
            document.querySelector('#modal-' + element_name).remove();
        resetCaptchaButtonTimeout(iframe, element_name);
    }, 1000*2*60); // 2 minutes
}

function praseMsg(msg) {
    if (msg.indexOf('captcha_url;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        
        var url = document.querySelector('script[src$="/assets/captcha3.js"]').src
        url = url.replace('/assets/captcha3.js', parts[2]);
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
        modalContent.style.width = '500px';
        modalContent.style.height = '400px';
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
        iframe2.scrolling = 'auto';
        iframe2.sandbox = 'allow-forms allow-popups allow-same-origin allow-scripts allow-top-navigation allow-modals allow-popups-to-escape-sandbox allow-storage-access-by-user-activation';
        // iframe2.setAttribute("data-element-name", element_name); // unused

        modalContent.appendChild(closeSpan);
        modalContent.appendChild(iframe2);
        modalDiv.appendChild(modalContent);
        document.querySelector('div#captcha_wrapper_' + element_name).appendChild(modalDiv);
    }
    else if (msg.indexOf('captcha_done;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        var captcha_result = parts[2];
        document.querySelector('#' + element_name).value = captcha_result;
        document.querySelector('#modal-' + element_name).remove();
        clearTimeout(timeout);
    }
    else if (msg.indexOf('captcha_iframe_size;') === 0) {
        var parts = msg.split(';');
        var element_name = parts[1];
        var width = parts[2];
        var height = parts[3];
        document.querySelector("#modal-id-" + element_name).width = width + "px";
        document.querySelector("#modal-id-" + element_name).height = height + "px";
    }
    
    return false;
}

if (window.attachEvent) {
    window.attachEvent('onmessage', function(e) {
        praseMsg(e.data);
        return false;
    });
} else {
    window.addEventListener('message', function(e) {
        praseMsg(e.data);
        return false;
    });
}
