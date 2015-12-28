angular.module('staticPages', [
    'ngRoute',
    'satellizer'
])

    .config(function($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })



    .controller("AboutPageCtrl", function($scope, $sce, $http, ngProgress){

    })

    .controller("LandingPageCtrl", function($scope, $auth, ngProgress){
        console.log("landing page!")
        ngProgress.complete()

        $scope.authenticate = function() {
            console.log("authenticate!")

            $auth.authenticate("twitter");
        };


    })










