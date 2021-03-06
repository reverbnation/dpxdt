/*
 * Copyright 2013 Brett Slatkin
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var fs = require('fs');
var system = require('system');


// Read and validate config.
var configPath = null;
var outputPath = null;
if (system.args.length == 3) {
    configPath = system.args[1];
    outputPath = system.args[2];
} else {
    console.log('Usage: phantomjs capture.js <config.js> <outputPath>');
    phantom.exit(1);
}

try {
    var config = JSON.parse(fs.read(configPath));
} catch (e) {
    console.log('Could not read config at "' + configPath + '":\n' + e);
    phantom.exit(1);
}

['targetUrl'].forEach(function(field) {
    if (!config[field]) {
        console.log('Missing required field: ' + field);
        phantom.exit(1);
    }
});

// Configure the page.
var page = require('webpage').create();

if (config.viewportSize) {
    page.viewportSize = {
        width: config.viewportSize.width,
        height: config.viewportSize.height
    };
}

if (config.clipRect) {
    page.clipRect = {
        left: 0,
        top: 0,
        width: config.clipRect.width,
        height: config.clipRect.height
    };
}

if (config.cookies) {
    config.cookies.forEach(function(cookie) {
        phantom.addCookie(cookie);
    });
}

// Do not load Google Analytics URLs. We don't want to pollute stats.
var badResources = [
    'www.google-analytics.com'
];

if (config.resourcesToIgnore) {
    badResources.forEach(function(bad) {
        config.resourcesToIgnore.push(bad);
    });
} else {
    config.resourcesToIgnore = badResources;
}

// Echo all console messages from the page to our log.
page.onConsoleMessage = function(message, line, source) {
    console.log('>> CONSOLE: ' + message);
};


// We don't necessarily want to load every resource a page asks for.
page.onResourceRequested = function(requestData, networkRequest) {
    config.resourcesToIgnore.forEach(function(bad) {
        if (requestData.url.match(new RegExp(bad))) {
            console.log('Blocking resource: ' + requestData.url);
            networkRequest.abort();
            return;
        }
    });
};

// Log all resources loaded as part of this request, for debugging.
page.onResourceReceived = function(response) {
    if (response.stage != 'end') {
        return;
    }
    if (response.url.indexOf('data:') == 0) {
        console.log('Loaded data URI');
    } else {
        console.log('Loaded: ' + response.url);
    }
};

// TODO: Username/password using HTTP basic auth
// TODO: Header key/value pairs
// TODO: User agent spoofing shortcut

/**
 * Just for debug logging.
 */
page.onInitialized = function() {
    console.log('page.onInitialized');
};


/**
 * Dumps out any error logs.
 * @param {string} msg The exception text.
 * @param {string} trace The exception trace.
 */
page.onError = function(msg, trace) {
    console.log('=( page.onError', msg, trace);
};


/**
 * Just for debug logging.
 */
page.onLoadFinished = function() {
    console.log('page.onLoadFinished');
};


/**
 * Our main screenshot routine.
 */
page.doDepictedScreenshots = function() {
    console.log('page.doDepictedScreenshots', outputPath);

    if (config.injectCss) {
        console.log('Injecting CSS: ' + config.injectCss);
        page.evaluate(function(config) {
            var styleEl = document.createElement('style');
            styleEl.type = 'text/css';
            styleEl.innerHTML = config.injectCss;
            document.getElementsByTagName('head')[0].appendChild(styleEl);
        }, config);
    }

    if (config.injectJs) {
        console.log('Injecting JS: ' + config.injectJs);
        page.evaluate(function(config) {
            window.eval(config.injectJs);
        }, config);
    }
    if (config.elementSelector) {
       // TODO: don't assume jQuery is loaded and called jQuery  

        /**
         *  Inheritance issue...eval to make sure elementSelector is in the windows scope
         */
        eval('function workaround(){ window.componentSelector = jQuery("' + config.elementSelector + '");}')
                page.evaluate(workaround);

        console.log('Selecting Element: ' + config.elementSelector);

        var rect = page.evaluate(function(){
            // find the component
            var element = jQuery(window.componentSelector);
            // get its bounding box
            var height = element.height();
            var width  = element.width();
            var box = element.position();
            // we want {top, left, width, height}
            box.width  = width;
            box.height = height;
            return box;
        });

        page.clipRect = rect;
        
    }
    // TODO: Do we need this setTimeout?
    window.setTimeout(function() {
        console.log('Taking the screenshot!');
        page.render(outputPath);
        phantom.exit(0);
    }, 10000);
};

// Screenshot
page.open(config.targetUrl, function(status) {
    console.log('Finished loading page:', config.targetUrl,
                'w/ status:', status);
    page.doDepictedScreenshots();
});
