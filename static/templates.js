angular.module('templates.app', ['landing.tpl.html']);

angular.module("landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing.tpl.html",
    "<div class=\"top-screen\" layout=\"row\" layout-align=\"center center\">\n" +
    "    <div class=\"content\">\n" +
    "\n" +
    "        <div class=\"no-doi demo-step\"\n" +
    "             ng-class=\"{'animated fadeOutDown': animation=='2start'}\"\n" +
    "             ng-hide=\"animation=='2start' || animation=='2finish'\">\n" +
    "\n" +
    "            <h1 class=\"animation-{{ !!animation }}\">\n" +
    "                <img src=\"https://i.imgur.com/cf9wXBR.png\" alt=\"\" class=\"logo\">\n" +
    "                Leap tall paywalls in a single bound.\n" +
    "            </h1>\n" +
    "\n" +
    "            <div class=\"under\">\n" +
    "                <div class=\"input-row\">\n" +
    "                    <md-input-container class=\"md-block example-selected-{{ main.exampleSelected }}\" flex-gt-sm=\"\">\n" +
    "                        <label ng-show=\"!animation\" class=\"animating-{{ animation }}\" >Paste your DOI here</label>\n" +
    "                        <input ng-model=\"main.doi\" ng-disabled=\"animation\">\n" +
    "                        <md-progress-circular md-diameter=\"20px\"></md-progress-circular>\n" +
    "\n" +
    "                    </md-input-container>\n" +
    "\n" +
    "                </div>\n" +
    "                <div class=\"text\">\n" +
    "                    <div class=\"example-doi\"\n" +
    "                         ng-class=\"{'animated fadeOut': animation}\"\n" +
    "                         ng-hide=\"animation\">\n" +
    "                        <span class=\"label\">or try this example: </span>\n" +
    "                        <span class=\"val\" ng-click=\"selectExample()\">http://doi.org/{{ exampleDoi }}</span>\n" +
    "                        <a href=\"http://doi.org/{{ exampleDoi }}\" target=\"_blank\">[paywall]</a>\n" +
    "                    </div>\n" +
    "\n" +
    "                </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "        <div class=\"has-results demo-step\"\n" +
    "             ng-class=\"{'animated fadeInDown': animation==='2finish'}\"\n" +
    "             ng-show=\"animation && animation==='2finish'\">\n" +
    "\n" +
    "            <div class=\"success\" ng-show=\"main.resp.free_fulltext_url\">\n" +
    "                <h1>We found an open version!</h1>\n" +
    "                <div class=\"under\">\n" +
    "                    <p class=\"read-here\">\n" +
    "                        This article is <a href=\"{{ main.resp.free_fulltext_url }}\" target=\"_blank\">free to read here</a> under a {{ main.resp.license }} license.\n" +
    "                    </p>\n" +
    "\n" +
    "\n" +
    "                    <div class=\"tip\" layout=\"row\">\n" +
    "                        <div class=\"label\">Pro&nbsp;tip:</div>\n" +
    "                        <div class=\"val\"> <em>Pro tip: </em> Save time by adding\n" +
    "                        <strong>\"oa\"</strong> to any DOI. For example,\n" +
    "\n" +
    "                        <a href=\"http://oadoi.org/{{ main.doi }}\" target=\"_blank\">http://<strong>oa</strong>doi.org/{{ main.doi }}</a>\n" +
    "                        will take you straight to the free version of this article.\n" +
    "                        </div>\n" +
    "                    </div>\n" +
    "\n" +
    "\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"failure\" ng-show=\"!main.resp.free_fulltext_url\">\n" +
    "                <h1>We could've find any open version.</h1>\n" +
    "                <div class=\"under\">\n" +
    "                    <p class=\"read-here\">\n" +
    "                        Sorry, it looks like no one archived a free-to-read copy of this\n" +
    "                        article. #paywallssuck.\n" +
    "                    </p>\n" +
    "                    <p class=\"try-again\">Care to <a href=\"\" ng-click=\"tryAgain()\" class=\"try-again\">try a different article?</a></p>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "</div>");
}]);
