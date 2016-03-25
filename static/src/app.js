angular.module('app', [
    // external libs

    'ngRoute',
    'ngMessages',
    'satellizer',

    'ngResource',
    'ngSanitize',
    'ngMaterial',

    'templates.app',  // this is how it accesses the cached templates in ti.js

    'staticPages',

    'badgeDefs',
    'personPage',
    'productPage',
    'settingsPage',
    'badgePage',
    'aboutPages',

    'numFormat'

]);




angular.module('app').config(function ($routeProvider,
                                       $authProvider,
                                       $mdThemingProvider,
                                       $locationProvider) {


    $locationProvider.html5Mode(true);

    // handle 404s by redirecting to landing page.
    $routeProvider.otherwise({ redirectTo: '/' })

    $mdThemingProvider.theme('default')
        .primaryPalette('deep-orange')
        .accentPalette("blue")


    var orcidLoginSettings = {
        name: "orcid-login",
        url: "/api/auth/orcid",
        clientId: "APP-PF0PDMP7P297AU8S",
        redirectUri: window.location.origin + "/login",
        authorizationEndpoint: "https://orcid.org/oauth/authorize",

        defaultUrlParams: ['response_type', 'client_id', 'redirect_uri'],
        requiredUrlParams: ['scope', 'show_login'],
        scope: ['/authenticate'],
        responseType: 'code',
        showLogin: 'true',
        responseParams: {
            code: 'code',
            clientId: 'clientId',
            redirectUri: 'redirectUri'
        }
    }
    $authProvider.oauth2(orcidLoginSettings)

    // this is for when we know the user has no ORCID,
    // so we want to redirect them to "sign up for ORCID" oath
    // screen instead of the "sign in to ORCID" screen like normal
    var orcidRegisterSettings = angular.copy(orcidLoginSettings)
    orcidRegisterSettings.name = "orcid-register"
    orcidRegisterSettings.showLogin = "false"
    $authProvider.oauth2(orcidRegisterSettings)






});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $auth,
                                   $location) {



    (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
            (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
        m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

    ga('create', 'UA-23384030-3', 'auto');


    $rootScope.$on('$routeChangeStart', function(next, current){
    })
    $rootScope.$on('$routeChangeSuccess', function(next, current){
        window.scrollTo(0, 0)
        ga('send', 'pageview', { page: $location.url() });

    })

    // load the intercom user
    var me = $auth.getPayload();
    if (me){
        var claimed_at = moment(me.claimed_at).unix()
        var intercomInfo = {
            app_id: "z93rnxrs",
            name: me.given_names + " " + me.family_name,
            user_id: me.sub, // orcid ID
            claimed_at: claimed_at
          }
        Intercom('boot', intercomInfo)
    }






    $rootScope.$on('$routeChangeError', function(event, current, previous, rejection){
        console.log("$routeChangeError")
        $location.path("/")
        window.scrollTo(0, 0)
    });




});





angular.module('app').controller('AppCtrl', function(
    $rootScope,
    $scope,
    $route,
    $location,
    NumFormat,
    $auth,
    $interval,
    $http,
    $mdDialog,
    $sce){

    $scope.auth = $auth
    $scope.numFormat = NumFormat
    $scope.moment = moment // this will break unless moment.js loads over network...

    $scope.global = {}

    $rootScope.$on('$routeChangeSuccess', function(next, current){
        $scope.global.showBottomStuff = true
        $scope.global.loggingIn = false
    })

    $scope.trustHtml = function(str){
        return $sce.trustAsHtml(str)
    }






    var redirectUri = window.location.origin + "/login"
    var orcidAuthUrl = "https://orcid.org/oauth/authorize" +
        "?client_id=APP-PF0PDMP7P297AU8S" +
        "&response_type=code" +
        "&scope=/authenticate" +
        "&redirect_uri=" + redirectUri

    // used in the nav bar, also for signup on the landing page.
    var authenticate = function (showLogin) {
        console.log("authenticate!")

        if (showLogin == "signin"){
            // will show the signup screen
        }
        else {
            // show the login screen (defaults to this)
            orcidAuthUrl += "&show_login=true"
        }

        window.location = orcidAuthUrl
        return true

    }

    $rootScope.authenticate = authenticate
    $scope.authenticate = authenticate

    var showAlert = function(msgText, titleText, okText){
        if (!okText){
            okText = "ok"
        }
          $mdDialog.show(
                  $mdDialog.alert()
                    .clickOutsideToClose(true)
                    .title(titleText)
                    .textContent(msgText)
                    .ok(okText)
            );
    }
    $rootScope.showAlert = showAlert









    /********************************************************
     *
     *  stripe stuff
     *
    ********************************************************/



    var stripeInfo = {
        email: null,
        tokenId: null,
        cents: 0,

        // optional
        fullName: null,
        orcidId: null
    }

    var stripeHandler = StripeCheckout.configure({
        key: stripePublishableKey,
        locale: 'auto',
        token: function(token) {
            stripeInfo.email = token.email
            stripeInfo.tokenId = token.id

            console.log("now we are doing things with the user's info", stripeInfo)
            $http.post("/api/donation", stripeInfo)
                .success(function(resp){
                    console.log("the credit card charge worked!", resp)
                    showAlert(
                        "We appreciate your donation, and we've emailed you a receipt.",
                        "Thanks so much!"
                    )
                })
                .error(function(resp){
                    console.log("error!", resp.message)
                    if (resp.message){
                        var reason = resp.message
                    }
                    else {
                        var reason = "Sorry, we had a server error! Drop us a line at team@impactstory.org and we'll fix it."
                    }
                    showAlert(reason, "Credit card error")
                })
        }
      });
    $scope.donate = function(cents){
        console.log("donate", cents)
        stripeInfo.cents = cents
        var me = $auth.getPayload() // this might break on the donate page.
        if (me){
            stripeInfo.fullName = me.given_names + " " + me.family_name
            stripeInfo.orcidId = me.sub
        }

        stripeHandler.open({
          name: 'Impactstory donation',
          description: "We're a US 501(c)3",
          amount: cents
        });
    }


});

