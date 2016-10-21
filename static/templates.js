angular.module('templates.app', ['landing.tpl.html']);

angular.module("landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing.tpl.html",
    "<div class=\"top-screen\" layout=\"row\" layout-align=\"center center\">\n" +
    "    <div class=\"content\">\n" +
    "\n" +
    "        <div class=\"enter-doi no-doi demo-step\"\n" +
    "             ng-class=\"{'animated fadeOutDown': animation=='2start'}\"\n" +
    "             ng-hide=\"animation=='2start' || animation=='2finish'\">\n" +
    "\n" +
    "            <h1 class=\"animation-{{ !!animation }}\">\n" +
    "                <img src=\"static/img/oadoi-logo.png\" alt=\"\" class=\"logo\">\n" +
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
    "        <div class=\"has-results demo-step\"\n" +
    "             ng-class=\"{'animated fadeInDown': animation==='2finish'}\"\n" +
    "             ng-show=\"animation && animation==='2finish'\">\n" +
    "\n" +
    "            <div class=\"gold-oa success result\" ng-show=\"main.resp.oa_color=='gold'\">\n" +
    "                <h1>This article is Gold Open Access.</h1>\n" +
    "                <div class=\"under\">\n" +
    "                    <span class=\"hybrid\" ng-show=\"main.resp.is_subscription_journal\">\n" +
    "                        It's published as Hybrid OA in a subscription journal.\n" +
    "                    </span>\n" +
    "                    <span class=\"not-hybrid\" ng-show=\"!main.resp.is_subscription_journal\">\n" +
    "                        <span class=\"type oa-journal\" ng-show=\"main.resp.doi_resolver == 'crossref'\">\n" +
    "                            Like a growing percentage of the research literature, it's published in an OA journal.\n" +
    "                        </span>\n" +
    "                        <span class=\"type oa-repo\" ng-show=\"main.resp.doi_resolver == 'datacite'\">\n" +
    "                            It's published in an OA repository.\n" +
    "                        </span>\n" +
    "                    </span>\n" +
    "\n" +
    "                    <a href=\"{{ main.resp.url }}\" class=\"oa-link\">Read it now.</a>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <div class=\"green-oa success result\" ng-show=\"main.resp.oa_color=='green'\">\n" +
    "                <h1>This article is Green Open Access</h1>\n" +
    "                <div class=\"under\">\n" +
    "                    The article was\n" +
    "                    <a href=\"{{ main.resp.url }}\">published behind a paywall,</a>\n" +
    "                    but we found a copy that’s\n" +
    "                    free to read<span ng-show=\"main.resp.is_boai_license\" class=\"full-oa\"> and reuse</span>.\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <div class=\"not-oa failure result\" ng-show=\"!main.resp.free_fulltext_url\">\n" +
    "                <h1>This article isn't open.</h1>\n" +
    "                <div class=\"under\">\n" +
    "                    It’s behind a paywall, and we couldn’t find a free copy anywhere. \n" +
    "                    Unfortunately, this is still true\n" +
    "                    <a href=\"https://arxiv.org/abs/1206.3664\">for around 80% of scholarly articles.</a>\n" +
    "                </div>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"license-info\">\n" +
    "                <span class=\"label\">License:</span>\n" +
    "                <span class=\"license not-specified\" ng-show=\"!main.resp.license\">\n" +
    "                    not specified\n" +
    "                </span>\n" +
    "                <span class=\"license partly-open\" ng-show=\"main.resp.license && !main.resp.is_boai_license\">\n" +
    "                    <a href=\"http://sparcopen.org/our-work/howopenisit/\">Partially open ({{ main.resp.license }})</a>\n" +
    "                </span>\n" +
    "                <span class=\"license fully-open\" ng-show=\"main.resp.license && main.resp.is_boai_license\">\n" +
    "                    <a href=\"http://sparcopen.org/our-work/howopenisit/\">Fully open ({{ main.resp.license }})</a>\n" +
    "                </span>\n" +
    "            </div>\n" +
    "            <div class=\"results-options\">\n" +
    "                <md-button ng-show=\"main.resp.free_fulltext_url\"\n" +
    "                   href=\"{{ main.resp.free_fulltext_url }}\"\n" +
    "                   target=\"_blank\"\n" +
    "                   class=\"oa-link md-raised\">Read it now</md-button>\n" +
    "                <md-button href=\"\" ng-click=\"tryAgain()\" class=\"try-again\">try another</md-button>\n" +
    "            </div>\n" +
    "\n" +
    "        </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "    </div>\n" +
    "    <div class=\"more\" ng-show=\"!animation || animation=='2finish'\">\n" +
    "        <i class=\"fa fa-chevron-down\"></i>\n" +
    "        Learn more\n" +
    "    </div>\n" +
    "</div>");
}]);
