angular.module('app', [
  // external libs

  'ngRoute',
  'ngMessages',
  'satellizer',

  'ngResource',
  'ngSanitize',

  'templates.app',  // this is how it accesses the cached templates in ti.js

  'staticPages',

  'badgeDefs',
  'personPage',
  //'tagPage',
  //'packagePage',
  //'footer',


  //'resourcesModule',
  //'pageService',
  'numFormat',
  'currentUserService'

]);




angular.module('app').config(function ($routeProvider,
                                       $authProvider,
                                       $locationProvider) {


  $locationProvider.html5Mode(true);


    $authProvider.oauth2({
      name: "orcid",
      url: "/api/auth/orcid",
      clientId: "APP-PF0PDMP7P297AU8S",
      redirectUri: window.location.origin,
      authorizationEndpoint: "https://orcid.org/oauth/authorize",

      defaultUrlParams: ['response_type', 'client_id', 'redirect_uri'],
      requiredUrlParams: ['scope'],
      scope: ['/authenticate'],
      responseType: 'code',
      responseParams: {
        code: 'code',
        clientId: 'clientId',
        redirectUri: 'redirectUri'
      }
    });

    $authProvider.google({
      url: '/auth/google',
      authorizationEndpoint: 'https://accounts.google.com/o/oauth2/auth',
      redirectUri: window.location.origin,
      requiredUrlParams: ['scope'],
      optionalUrlParams: ['display'],
      scope: ['profile', 'email'],
      scopePrefix: 'openid',
      scopeDelimiter: ' ',
      display: 'popup',
      type: '2.0',
      popupOptions: { width: 452, height: 633 }
    });

});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $location) {





  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-23384030-3', 'auto');



  $rootScope.$on('$routeChangeStart', function(next, current){
    console.log("route change start")
  })
  $rootScope.$on('$routeChangeSuccess', function(next, current){
    console.log("route change success")
    window.scrollTo(0, 0)
    ga('send', 'pageview', { page: $location.url() });

  })
  $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
    console.log("$routeChangeError")
    $location.path("/")

    window.scrollTo(0, 0)

  });


  // from http://cwestblog.com/2012/09/28/javascript-number-getordinalfor/
  (function(o) {
    Number.getOrdinalFor = function(intNum, includeNumber) {
      return (includeNumber ? intNum : "")
        + (o[((intNum = Math.abs(intNum % 100)) - 20) % 10] || o[intNum] || "th");
    };
  })([,"st","nd","rd"]);




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


angular.module('app').controller('AppCtrl', function(
  $rootScope,
  $scope,
  $location,
  CurrentUser,
  NumFormat,
  $auth,
  $sce){


    $scope.auth = $auth
    //$scope.currentUser = CurrentUser
    //CurrentUser.get()

    $scope.numFormat = NumFormat


    $scope.iconUrl = function(){
        var payload = $auth.getPayload()
        if (payload) {
            return payload.picture
        }
        else {
            return ""
        }
    }

  $scope.trustHtml = function(str){
    console.log("trusting html:", str)
    return $sce.trustAsHtml(str)
  }


  $scope.$on('$locationChangeStart', function(event, next, current){
  })


});

