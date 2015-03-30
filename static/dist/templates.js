angular.module('templates.app', ['landing-page/landing.tpl.html']);

angular.module("landing-page/landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing-page/landing.tpl.html",
    "<div class=\"landing\">\n" +
    "   <h1><img src=\"static/img/impactstory-biomed.png\" alt=\"Impactstory Biomed\"/></h1>\n" +
    "\n" +
    "\n" +
    "   <form class=\"create-profile\" ng-submit=\"makeProfile()\">\n" +
    "\n" +
    "      <div class=\"form-group\">\n" +
    "         <input type=\"text\"\n" +
    "                autofocus=\"autofocus\"\n" +
    "                class=\"form-control input-lg\"\n" +
    "                ng-model=\"newProfile.name\"\n" +
    "                placeholder=\"What is your name?\"/>\n" +
    "\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"form-group\">\n" +
    "         <textarea class=\"form-control input-lg\"\n" +
    "                   ng-model=\"newProfile.pmids\"\n" +
    "                   placeholder=\"What are your PubMed IDs?\"\n" +
    "                   rows=\"5\"></textarea>\n" +
    "\n" +
    "      </div>\n" +
    "      <div class=\"submit-btn-container\">\n" +
    "         <button type=\"submit\" class=\"btn submit btn-lg btn-default\">\n" +
    "            Find my impact\n" +
    "         </button>\n" +
    "      </div>\n" +
    "\n" +
    "   </form>\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);
