angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginPageCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http) {

    })


    .controller("LoginPageCtrl", function ($scope, $sce, $http) {
        console.log("login page controller is running!")

    })

    .controller("LandingPageCtrl", function ($scope, $rootScope, $http, $auth, $location) {
        console.log("landing page!", $scope.global)
        $scope.global.isLandingPage = true


        $scope.authenticate = function () {
            console.log("authenticate!")

            $auth.authenticate("orcid")
                .then(function(resp){
                    var orcid_id = $auth.getPayload()['sub']
                    console.log("you have successfully logged in!", resp, $auth.getPayload())

                    // take the user to their profile.
                    $location.path("/u/" + orcid_id)

                })
                .catch(function(error){
                    console.log("there was an error logging in:", error)
                })
        };



    })










