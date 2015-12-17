angular.module('top', [
    'ngRoute',
    'filterService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/leaderboard', {
      templateUrl: 'top/top.tpl.html',
      controller: 'TopController',
      resolve: {

      }
    })
  })


  .controller("TopController", function($scope,
                                          $http,
                                          $rootScope,
                                          $routeParams,
                                          Leaders,
                                          ngProgress,
                                          FormatterService,
                                          FilterService){
    FilterService.setFromUrl()
    $scope.filters = FilterService
    $scope.format = FormatterService

    getLeaders()

    var makeUrl = function(){
      return "leaderboard?" + FilterService.asQueryStr()
    }

    function getLeaders(){
      console.log("getLeaders() go", FilterService.d)


      Leaders.get(
        FilterService.d,
        function(resp){
          console.log("got a resp from leaders call", resp.list)
          $scope.leaders = resp
          ngProgress.complete()
        },
        function(resp){
          console.log("got an error :(")
          ngProgress.complete()
        }
      )

    }



















  })
