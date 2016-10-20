angular.module('landing', [
    'ngRoute',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/landing/:landingPageName', {
            templateUrl: "landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    .controller("LandingPageCtrl", function ($scope,
                                             $http,
                                             $timeout) {

        console.log("i am the landing page ctrl")
        $scope.main = {
            step: "no-doi"
        }

        $scope.animation = null

        var animate = function(step){
            $scope.animation = step + "start"
            console.log("set animation", $scope.animation)
            $timeout(function(){
                $scope.animation = step + "finish"
                console.log("set animation", $scope.animation)
            }, 505)
        }

        var baseUrl = "http://api.oadoi.org/v1/publication/doi/"
        $scope.exampleDoi = "10.1016/j.tree.2007.03.007"

        $scope.$watch(function(s){return s.main.doi }, function(newVal, oldVal){
            console.log("doi change", newVal, oldVal)
            if (!newVal){
                return false
            }
            if (newVal.indexOf("10.") === 0) {
                animate(1)
                $http.get(baseUrl + newVal)
                    .success(function(resp){
                        console.log("got response back", resp.results[0])
                        if (newVal == $scope.exampleDoi){
                            console.log("this is the sample DOI...waiting to return result.")
                            $timeout(function(){
                                console.log("returning the result now")
                                animate(2)
                                $scope.main.resp = resp.results[0]
                            }, 5000)
                        }
                        else {
                            animate(2)
                            $scope.main.resp = resp.results[0]
                        }


                    })
            }
        })

    })










