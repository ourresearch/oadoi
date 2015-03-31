/* yay impactstory */
angular.module('app', [
  'ngRoute', // loaded from external lib
  'templates.app',  // this is how it accesses the cached templates in ti.js

  'landingPage'
]);




angular.module('app').config(function ($routeProvider,
                                       $locationProvider) {
  $locationProvider.html5Mode(true);
//  paginationTemplateProvider.setPath('directives/pagination.tpl.html')
});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $location) {

  /*
  this lets you change the args of the URL without reloading the whole view. from
     - https://github.com/angular/angular.js/issues/1699#issuecomment-59283973
     - http://joelsaupe.com/programming/angularjs-change-path-without-reloading/
     - https://github.com/angular/angular.js/issues/1699#issuecomment-60532290
  */
  var original = $location.path;
  $location.path = function (path, reload) {
      if (reload === false) {
          var lastRoute = $route.current;
          var un = $rootScope.$on('$locationChangeSuccess', function () {
              $route.current = lastRoute;
              un();
          });
        $timeout(un, 500)
      }
      return original.apply($location, [path]);
  };

});


angular.module('app').controller('AppCtrl', function($scope){

  console.log("we loaded the app controller (AppCtrl)")
  /*
  $scope.$on('$routeChangeError', function(event, current, previous, rejection){
    RouteChangeErrorHandler.handle(event, current, previous, rejection)
  });

  $scope.$on('$routeChangeSuccess', function(next, current){
    security.requestCurrentUser().then(function(currentUser){
      Page.sendPageloadToSegmentio()
    })
  })

  $scope.$on('$locationChangeStart', function(event, next, current){
    ProductPage.loadingBar(next, current)
    Page.setProfileUrl(false)
    Loading.clear()
  })

  */

});


angular.module('landingPage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/', {
      templateUrl: 'landing-page/landing.tpl.html',
      controller: 'landingPageCtrl'
    })
  })



  .controller("landingPageCtrl", function($scope, ProfileService){
    console.log("loaded the landing page controller")
    $scope.newProfile = {}
    $scope.makeProfile = function(){
      ProfileService.createProfile(
        $scope.newProfile.name,
        $scope.newProfile.pmids.split("\n")
      )

    }

  })



angular.module('profileService', [
  ])



  .factory("ProfileService", function($http){
    return {
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids) {
        console.log("i am making a profile:", name, pmids)
        var postData = {
          name: name,
          pmids: pmids
        }
        $http.post("/profile",postData)
          .success(function(resp, status, headers){
            console.log("yay got a resp from /profile!", resp)
          })
      }
    }


  })
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
